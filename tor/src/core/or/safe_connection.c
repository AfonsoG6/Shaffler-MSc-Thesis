#include "core/or/safe_connection.h"
#include "app/config/config.h"
#include "lib/net/buffers_net.h"
#include "lib/tls/tortls.h"
#include "lib/tls/buffers_tls.h"
#include "lib/malloc/malloc.h"
#include "core/proto/proto_cell.h"
#include "core/or/connection_or.h"
#include "core/or/var_cell_st.h"
#include "core/or/cell_st.h"
#include "core/or/cell_queue_st.h"
#include "core/mainloop/throughput_logging.h"

event_label_t safe_or_conn_tcp_connecting_ev = EVENT_LABEL_UNSET;
event_label_t safe_or_conn_tls_handshaking_ev = EVENT_LABEL_UNSET;
event_label_t safe_or_conn_link_handshaking_ev = EVENT_LABEL_UNSET;
event_label_t safe_or_conn_open_ev = EVENT_LABEL_UNSET;
event_label_t safe_or_conn_closed_ev = EVENT_LABEL_UNSET;
event_label_t safe_or_conn_fixed_cell_ev = EVENT_LABEL_UNSET;
event_label_t safe_or_conn_var_cell_ev = EVENT_LABEL_UNSET;

static void
safe_connection_refresh_events(safe_connection_t *safe_conn);

static void
safe_or_connection_refresh_bucket_rw_states(safe_or_connection_t *safe_or_conn);

static void
safe_or_conn_link_protocol_version_cb(event_label_t label, event_data_t data,
                                      void *context);

static void
safe_or_conn_open_cb(event_label_t label, event_data_t data, void *context);

static void
safe_or_conn_closed_cb(event_label_t label, event_data_t data, void *context);

static tor_error_t
safe_or_connection_update_state(safe_or_connection_t *safe_or_conn,
                                or_conn_state_t new_state);

static bool
safe_or_connection_is_read_wanted(safe_connection_t *safe_conn);

static bool
safe_or_connection_is_write_wanted(safe_connection_t *safe_conn);

static void
safe_or_connection_read_cb(safe_connection_t *safe_conn);

static void
safe_or_connection_write_cb(safe_connection_t *safe_conn);

static void
safe_or_connection_socket_added_cb(safe_connection_t *safe_conn);

static void
safe_or_connection_outbuf_modified_cb(safe_connection_t *safe_conn);

static void
safe_or_conn_outgoing_cell_cb(event_label_t label, event_data_t data,
                              void *context);

static void
process_cells_from_inbuf(safe_or_connection_t *safe_or_conn);

/********************************************************/

safe_or_connection_t *
TO_SAFE_OR_CONN(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_assert(safe_conn->magic == SAFE_OR_CONN_MAGIC);
  return DOWNCAST(safe_or_connection_t, safe_conn);
}

void
safe_or_conn_register_events(event_registry_t *registry)
{
  tor_assert(safe_or_conn_tcp_connecting_ev == EVENT_LABEL_UNSET);
  tor_assert(safe_or_conn_tls_handshaking_ev == EVENT_LABEL_UNSET);
  tor_assert(safe_or_conn_link_handshaking_ev == EVENT_LABEL_UNSET);
  tor_assert(safe_or_conn_open_ev == EVENT_LABEL_UNSET);
  tor_assert(safe_or_conn_closed_ev == EVENT_LABEL_UNSET);
  tor_assert(safe_or_conn_fixed_cell_ev == EVENT_LABEL_UNSET);
  tor_assert(safe_or_conn_var_cell_ev == EVENT_LABEL_UNSET);

  safe_or_conn_tcp_connecting_ev = \
    event_registry_register_event(registry, "OR Connection Connecting");
  safe_or_conn_tls_handshaking_ev = \
    event_registry_register_event(registry, "Starting OR TLS Handshake");
  safe_or_conn_link_handshaking_ev = \
    event_registry_register_event(registry, "Starting OR Link Handshake");
  safe_or_conn_open_ev = \
    event_registry_register_event(registry, "OR Connection Open");
  safe_or_conn_closed_ev = \
    event_registry_register_event(registry, "OR Connection Closed");
  safe_or_conn_fixed_cell_ev = \
    event_registry_register_event(registry, "OR Connection New Fixed-Size Cell");
  safe_or_conn_var_cell_ev = \
    event_registry_register_event(registry, "OR Connection New Variable-Size Cell");
}

/********************************************************/

void
link_handshaking_ev_free(void *ptr)
{
  // we don't need to free the certs since we passed the ownership
  tor_free(ptr);
}

/********************************************************/

static void
socket_rw_state_init(socket_rw_state_t *rw_state,
                     bool initial_state)
{
  tor_assert(rw_state != NULL);

  rw_state->state = initial_state;
}

static bool
socket_rw_state_get(socket_rw_state_t *rw_state)
{
  tor_assert(rw_state != NULL);

  return rw_state->state;
}

static void
socket_rw_state_set(socket_rw_state_t *rw_state,
                    bool new_state,
                    safe_connection_t *safe_conn)
{
  tor_assert(rw_state != NULL);
  tor_assert(safe_conn != NULL);

  if (new_state != rw_state->state) {
    rw_state->state = new_state;
    safe_connection_refresh_events(safe_conn);
  }
}

/********************************************************/

/*
void
safe_cell_queue_init(safe_cell_queue_t *queue)
{
  tor_assert(queue != NULL);
  memset(queue, 0, sizeof(*queue));

  tor_mutex_init(&queue->lock);
  TOR_SIMPLEQ_INIT(&queue->head);
}

void
safe_cell_queue_append(safe_cell_queue_t *queue,
                       generic_cell_t *cell)
{
  tor_assert(queue != NULL);
  tor_assert(cell != NULL);
  tor_mutex_acquire(&queue->lock);

  TOR_TAILQ_INSERT_TAIL(&queue->head, cell);

  tor_mutex_release(&queue->lock);
}

generic_cell_t *
safe_cell_queue_pop(safe_cell_queue_t *queue)
{

}
*/

/********************************************************/

void
safe_connection_init(safe_connection_t *safe_conn, uint32_t type_magic,
                     event_source_t *conn_event_source,
                     bool (*is_read_wanted)(safe_connection_t *),
                     bool (*is_write_wanted)(safe_connection_t *),
                     void (*read_cb)(safe_connection_t *),
                     void (*write_cb)(safe_connection_t *),
                     void (*socket_added_cb)(safe_connection_t *),
                     void (*inbuf_modified_cb)(safe_connection_t *),
                     void (*outbuf_modified_cb)(safe_connection_t *),
                     bool requires_buffers, bool linked)
{
  (void)conn_event_source;

  tor_assert(safe_conn != NULL);
  tor_assert(is_read_wanted != NULL);
  tor_assert(is_write_wanted != NULL);
  tor_assert(read_cb != NULL);
  tor_assert(write_cb != NULL);

  memset(safe_conn, 0, sizeof(*safe_conn));

  safe_conn->magic = type_magic;
  safe_conn->socket = TOR_INVALID_SOCKET;
  safe_conn->linked = linked;

  safe_conn->event_source = event_source_new();
  safe_conn->event_listener = event_listener_new(safe_conn);

  socket_rw_state_init(&safe_conn->read_allowed, true);
  socket_rw_state_init(&safe_conn->write_allowed, true);

  tor_mutex_init(&safe_conn->lock);

  safe_conn->is_read_wanted = is_read_wanted;
  safe_conn->is_write_wanted = is_write_wanted;
  safe_conn->read_cb = read_cb;
  safe_conn->write_cb = write_cb;
  safe_conn->socket_added_cb = socket_added_cb;
  safe_conn->inbuf_modified_cb = inbuf_modified_cb;
  safe_conn->outbuf_modified_cb = outbuf_modified_cb;

  if (requires_buffers) {
    safe_conn->inbuf = buf_new();
    safe_conn->outbuf = buf_new();
  }

  safe_conn->care_about_modified = true;
}

void
safe_connection_set_socket(safe_connection_t *safe_conn, tor_socket_t socket)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);
  tor_assert(!safe_conn->linked);
  tor_assert(SOCKET_OK(socket));

  if (SOCKET_OK(safe_conn->socket)) {
    log_warn(LD_BUG, "We're overwriting a previous socket");
  }
  safe_conn->socket = socket;

  if (safe_conn->socket_added_cb != NULL) {
    safe_conn->socket_added_cb(safe_conn);
  }

  tor_mutex_release(&safe_conn->lock);
}

static void
safe_connection_close_socket(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  safe_connection_unregister_events(safe_conn);
  event_listener_detach(safe_conn->event_listener);
  // assume it's safe at this point we don't care about any more events
  // TODO: improve this (possibly with something like a sentinel event)

  if (SOCKET_OK(safe_conn->socket)) {
    tor_close_socket(safe_conn->socket);
    safe_conn->socket = TOR_INVALID_SOCKET;
  }

  tor_mutex_release(&safe_conn->lock);
}

static void
safe_connection_read_cb(evutil_socket_t ev_sock, short fd, void *void_safe_conn)
{
  (void)ev_sock;
  (void)fd;
  safe_connection_t *safe_conn = void_safe_conn;

  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);
  tor_assert(safe_conn->read_cb != NULL);
  //tor_assert(safe_conn->read_event != NULL);

  // NOTE: the below requires obtaining a lock on the event base, which adds
  //       unnecessary slowness
  // XX: Is the above true?
  //if (!event_pending(safe_conn->read_event, EV_READ, NULL)) {
  //  // another thread may have disabled this event between when the
  //  // callback started, and when we acquired the lock above
  //  return;
  //}

  //if (!safe_conn->read_allowed || !safe_conn->read_wanted) {
  //  // we shouldn't be reading
  //  return;
  //}

  safe_conn->read_cb(safe_conn);

  tor_mutex_release(&safe_conn->lock);
}

static void
safe_connection_write_cb(evutil_socket_t ev_sock, short fd, void *void_safe_conn)
{
  (void)ev_sock;
  (void)fd;
  safe_connection_t *safe_conn = void_safe_conn;

  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);
  tor_assert(safe_conn->write_cb != NULL);
  //tor_assert(safe_conn->write_event != NULL);

  // NOTE: the below requires obtaining a lock on the event base, which adds
  //       unnecessary slowness
  // XX: Is the above true?
  //if (!event_pending(safe_conn->write_event, EV_WRITE, NULL)) {
  //  // another thread may have disabled this event between when the
  //  // callback started, and when we acquired the lock above
  //  return;
  //}

  //if (!safe_conn->write_allowed || !safe_conn->write_wanted) {
  //  // we shouldn't be writing
  //  return;
  //}

  safe_conn->write_cb(safe_conn);

  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_subscribe(safe_connection_t *safe_conn,
                          event_listener_t *listener, event_label_t label)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  event_source_subscribe(safe_conn->event_source, listener, label);

  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_unsubscribe_all(safe_connection_t *safe_conn,
                                event_listener_t *listener)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  event_source_unsubscribe_all(safe_conn->event_source, listener);

  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_unregister_events(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  if (safe_conn->read_event != NULL) {
    tor_event_free(safe_conn->read_event);
  }
  if (safe_conn->write_event != NULL) {
    tor_event_free(safe_conn->write_event);
  }

  // we may still want to receive events, so we don't detach the
  // event listener yet
  // TODO: figure out a better way of handling this

  tor_mutex_release(&safe_conn->lock);
}

tor_error_t
safe_connection_register_events(safe_connection_t *safe_conn,
                                struct event_base *event_base)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);
  tor_assert(safe_conn->read_cb != NULL);
  tor_assert(safe_conn->write_cb != NULL);
  tor_assert(safe_conn->linked != SOCKET_OK(safe_conn->socket));
  // is either linked or has a socket, but not both (or neither)

  safe_connection_unregister_events(safe_conn);
  event_listener_detach(safe_conn->event_listener);

  safe_conn->read_event = tor_event_new(event_base, safe_conn->socket,
                                        EV_READ|EV_PERSIST,
                                        safe_connection_read_cb, safe_conn);
  safe_conn->write_event = tor_event_new(event_base, safe_conn->socket,
                                         EV_WRITE|EV_PERSIST,
                                         safe_connection_write_cb, safe_conn);

  if (safe_conn->read_event == NULL || safe_conn->write_event == NULL) {
    log_warn(LD_BUG, "Could not set events for %d", (int)safe_conn->socket);
    safe_connection_unregister_events(safe_conn);
    tor_mutex_release(&safe_conn->lock);
    return E_ERROR;
  }

  event_listener_attach(safe_conn->event_listener, event_base);

  safe_connection_refresh_events(safe_conn);

  tor_mutex_release(&safe_conn->lock);
  return E_SUCCESS;
}

static void
safe_connection_refresh_events(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);
  tor_assert(safe_conn->is_read_wanted != NULL);
  tor_assert(safe_conn->is_write_wanted != NULL);

  if (safe_conn->read_event != NULL) {
    if (socket_rw_state_get(&safe_conn->read_allowed) &&
        safe_conn->is_read_wanted(safe_conn)) {
      event_add(safe_conn->read_event, NULL);
    } else {
      event_del(safe_conn->read_event);
    }
  }

  if (safe_conn->write_event != NULL) {
    if (socket_rw_state_get(&safe_conn->write_allowed) &&
        safe_conn->is_write_wanted(safe_conn)) {
      event_add(safe_conn->write_event, NULL);
    } else {
      event_del(safe_conn->write_event);
    }
  }

  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_set_read_permission(safe_connection_t *safe_conn,
                                    bool read_allowed)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);
  socket_rw_state_set(&safe_conn->read_allowed, read_allowed, safe_conn);
  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_set_write_permission(safe_connection_t *safe_conn,
                                     bool write_allowed)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);
  socket_rw_state_set(&safe_conn->write_allowed, write_allowed, safe_conn);
  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_start_caring_about_modified(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  safe_conn->care_about_modified = true;

  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_stop_caring_about_modified(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  safe_conn->care_about_modified = false;

  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_inbuf_modified(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  if (safe_conn->inbuf_modified_cb != NULL && safe_conn->care_about_modified) {
    safe_conn->inbuf_modified_cb(safe_conn);
  }

  tor_mutex_release(&safe_conn->lock);
}

void
safe_connection_outbuf_modified(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  tor_mutex_acquire(&safe_conn->lock);

  if (safe_conn->outbuf_modified_cb != NULL && safe_conn->care_about_modified) {
    safe_conn->outbuf_modified_cb(safe_conn);
  }
  
  tor_mutex_release(&safe_conn->lock);
}

//void
//safe_connection_use_inbuf(safe_connection_t *safe_conn,
//                          int (*f)(struct buf_t *, void *, void **),
//                          void *data,
//                          void **ret_val)
//{
//  tor_assert(safe_conn != NULL);
//  tor_assert(f != NULL);
//  tor_mutex_acquire(&safe_conn->lock);
//
//  int rv = f(safe_conn->inbuf, data, ret_val);
//
//  tor_mutex_release(&safe_conn->lock);
//
//  return rv;
//}

/********************************************************/

safe_or_connection_t *
safe_or_connection_new(bool requires_buffers, bool is_outgoing,
                       const char *remote_address_str,
                       event_source_t *conn_event_source)
{
  safe_or_connection_t *safe_or_conn = \
    tor_malloc_zero(sizeof(safe_or_connection_t));

  safe_connection_init(TO_SAFE_CONN(safe_or_conn),
                       SAFE_OR_CONN_MAGIC,
                       conn_event_source,
                       safe_or_connection_is_read_wanted,
                       safe_or_connection_is_write_wanted,
                       safe_or_connection_read_cb,
                       safe_or_connection_write_cb,
                       safe_or_connection_socket_added_cb,
                       NULL,
                       safe_or_connection_outbuf_modified_cb,
                       requires_buffers, false);

  token_bucket_rw_init(&safe_or_conn->bucket, 1, 1, time(NULL));
  safe_or_conn->is_outgoing = is_outgoing;
  if (remote_address_str != NULL) {
    safe_or_conn->remote_address_str = \
      tor_strdup(escaped_safe_str(remote_address_str));
    // the function 'escaped_safe_str' must be run in the main thread
  } else {
    safe_or_conn->remote_address_str = NULL;
    log_warn(LD_OR, "No remote address string was provided");
  }

  event_listener_set_callback(TO_SAFE_CONN(safe_or_conn)->event_listener,
                              or_conn_link_protocol_version_ev,
                              NULL, safe_or_conn_link_protocol_version_cb);
  event_listener_set_callback(TO_SAFE_CONN(safe_or_conn)->event_listener,
                              or_conn_open_ev,
                              NULL, safe_or_conn_open_cb);
  event_listener_set_callback(TO_SAFE_CONN(safe_or_conn)->event_listener,
                              or_conn_closed_ev,
                              NULL, safe_or_conn_closed_cb);
  event_listener_set_callback(TO_SAFE_CONN(safe_or_conn)->event_listener,
                              or_conn_outgoing_packed_cell,
                              NULL, safe_or_conn_outgoing_cell_cb);
  event_listener_set_callback(TO_SAFE_CONN(safe_or_conn)->event_listener,
                              or_conn_outgoing_fixed_cell,
                              NULL, safe_or_conn_outgoing_cell_cb);
  event_listener_set_callback(TO_SAFE_CONN(safe_or_conn)->event_listener,
                              or_conn_outgoing_variable_cell,
                              NULL, safe_or_conn_outgoing_cell_cb);

  if (conn_event_source) {
    event_source_subscribe(conn_event_source,
                           TO_SAFE_CONN(safe_or_conn)->event_listener,
                           or_conn_link_protocol_version_ev);
    event_source_subscribe(conn_event_source,
                           TO_SAFE_CONN(safe_or_conn)->event_listener,
                           or_conn_open_ev);
    event_source_subscribe(conn_event_source,
                           TO_SAFE_CONN(safe_or_conn)->event_listener,
                           or_conn_closed_ev);
    event_source_subscribe(conn_event_source,
                           TO_SAFE_CONN(safe_or_conn)->event_listener,
                           or_conn_outgoing_packed_cell);
    event_source_subscribe(conn_event_source,
                           TO_SAFE_CONN(safe_or_conn)->event_listener,
                           or_conn_outgoing_fixed_cell);
    event_source_subscribe(conn_event_source,
                           TO_SAFE_CONN(safe_or_conn)->event_listener,
                           or_conn_outgoing_variable_cell);
  }

  event_source_deliver_silently(TO_SAFE_CONN(safe_or_conn)->event_source,
                                safe_or_conn_var_cell_ev, true);
  event_source_deliver_silently(TO_SAFE_CONN(safe_or_conn)->event_source,
                                safe_or_conn_fixed_cell_ev, true);

  safe_or_conn->link_protocol = 0; // unknown protocol
  safe_or_conn->wide_circ_ids = false;
  safe_or_conn->waiting_for_link_protocol = false;

  // these states should be set by 'safe_or_connection_update_state()'
  socket_rw_state_init(&safe_or_conn->tor_read_wanted,  false);
  socket_rw_state_init(&safe_or_conn->tor_write_wanted, false);
  socket_rw_state_init(&safe_or_conn->tls_read_wanted,  false);
  socket_rw_state_init(&safe_or_conn->tls_write_wanted, false);
  socket_rw_state_init(&safe_or_conn->bucket_read_allowed,  false);
  socket_rw_state_init(&safe_or_conn->bucket_write_allowed, false);
  safe_or_connection_refresh_bucket_rw_states(safe_or_conn);

  tor_assert(safe_or_connection_update_state(safe_or_conn,
    SAFE_OR_CONN_STATE_NO_SOCKET) == E_SUCCESS);

  return safe_or_conn;
}

static void
safe_or_connection_socket_added_cb(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);

  tor_assert(safe_or_connection_update_state(TO_SAFE_OR_CONN(safe_conn),
    SAFE_OR_CONN_STATE_TCP_CONNECTING) == E_SUCCESS);
  // it might already be connected, but it should be fine to transition
  // through this state first
}

static void
safe_or_connection_outbuf_modified_cb(safe_connection_t *safe_conn)
{
  log_warn(LD_OR, "Nothing should write directly to an OR conn buffer");
  tor_assert(0);

  tor_assert(safe_conn != NULL);
  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(safe_conn);

  if (safe_or_conn->state == SAFE_OR_CONN_STATE_LINK_HANDSHAKING ||
      safe_or_conn->state == SAFE_OR_CONN_STATE_OPEN) {
    if (buf_datalen(TO_SAFE_CONN(safe_or_conn)->outbuf) > 0) {
      socket_rw_state_set(&safe_or_conn->tor_write_wanted, true,
                          TO_SAFE_CONN(safe_or_conn));
    }
  } else {
    log_warn(LD_OR, "The outbuf was modified when in a state where it "
                    "shouldn't be modified (state %d)", safe_or_conn->state);
  }
}

static void
safe_or_connection_refresh_bucket_rw_states(safe_or_connection_t *safe_or_conn)
{
  if (token_bucket_rw_get_read(&safe_or_conn->bucket) > 0) {
    // token bucket is not empty, so we can read now
    socket_rw_state_set(&safe_or_conn->bucket_read_allowed, true,
                        TO_SAFE_CONN(safe_or_conn));
    log_debug(LD_OR, "Token bucket for %p read is non-empty", safe_or_conn);
  } else {
    // token bucket is empty, so can't read now
    socket_rw_state_set(&safe_or_conn->bucket_read_allowed, false,
                        TO_SAFE_CONN(safe_or_conn));
    log_debug(LD_OR, "Token bucket for %p read is empty", safe_or_conn);
  }
  if (token_bucket_rw_get_write(&safe_or_conn->bucket) > 0) {
    // token bucket is not empty, so we can write now
    socket_rw_state_set(&safe_or_conn->bucket_write_allowed, true,
                        TO_SAFE_CONN(safe_or_conn));
    log_debug(LD_OR, "Token bucket for %p write is non-empty", safe_or_conn);
  } else {
    // token bucket is empty, so can't write now
    socket_rw_state_set(&safe_or_conn->bucket_write_allowed, false,
                        TO_SAFE_CONN(safe_or_conn));
    log_debug(LD_OR, "Token bucket for %p write is empty", safe_or_conn);
  }
}

static void
safe_or_conn_link_protocol_version_cb(event_label_t label, event_data_t data,
                                      void *context)
{
  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(context);
  tor_assert(label == or_conn_link_protocol_version_ev);
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);
  tor_assert(safe_or_conn->state == SAFE_OR_CONN_STATE_LINK_HANDSHAKING);
  tor_assert(safe_or_conn->waiting_for_link_protocol);

  uint16_t link_protocol = data.u16;
  tor_assert(link_protocol >= 3);

  safe_or_conn->link_protocol = link_protocol;
  safe_or_conn->wide_circ_ids = (link_protocol >= 3);
  safe_or_conn->waiting_for_link_protocol = false;
  event_active(TO_SAFE_CONN(safe_or_conn)->read_event, 0, 0);
  // we need to process incoming cells on the buffer, even if there's
  // no data waiting on the incoming socket

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
}

static void
safe_or_conn_open_cb(event_label_t label, event_data_t data, void *context)
{
  (void)data;

  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(context);
  tor_assert(label == or_conn_open_ev);
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);
  tor_assert(safe_or_conn->state == SAFE_OR_CONN_STATE_LINK_HANDSHAKING ||
             safe_or_conn->state == SAFE_OR_CONN_STATE_CLOSED);

  if (safe_or_conn->state != SAFE_OR_CONN_STATE_CLOSED) {
    // if we're already closed, then just ignore it
    safe_or_connection_update_state(safe_or_conn, SAFE_OR_CONN_STATE_OPEN);
  }

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
}

static void
safe_or_conn_closed_cb(event_label_t label, event_data_t data, void *context)
{
  (void)data;

  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(context);
  tor_assert(label == or_conn_closed_ev);
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);

  // TODO: we should support closing forcefully and closing gracefully
  // with a CLOSING state (which only flushes remaining data)

  if (safe_or_conn->state != SAFE_OR_CONN_STATE_CLOSED) {
    // if we're already closed, then just ignore it
    safe_or_connection_update_state(safe_or_conn, SAFE_OR_CONN_STATE_CLOSED);
  }

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
}

// TODO: we should get rid of this at some point
void
safe_or_connection_get_tls_desc(safe_or_connection_t *safe_or_conn,
                                char *buf, size_t buf_size)
{
  tor_assert(safe_or_conn != NULL);
  tor_assert(buf != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);

  if (safe_or_conn->tls != NULL) {
    tor_tls_get_state_description(safe_or_conn->tls, buf, buf_size);
  } else {
    tor_snprintf(buf, buf_size, "<no tls object>");
  }

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
}

int
safe_or_connection_tls_secrets(safe_or_connection_t *safe_or_conn,
                               uint8_t *secrets_out)
{
  tor_assert(safe_or_conn != NULL);
  tor_assert(secrets_out != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);

  int rv = -1;

  if (safe_or_conn->tls == NULL){
    log_warn(LD_OR, "safe_or_conn->tls is NULL");
  } else {
    rv = tor_tls_get_tlssecrets(safe_or_conn->tls, secrets_out);
  }

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
  return rv;
}

int
safe_or_connection_key_material(safe_or_connection_t *safe_or_conn,
                                uint8_t *secrets_out,
                                const uint8_t *context,
                                size_t context_len, const char *label)
{
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);

  int rv = -1;

  if (safe_or_conn->tls == NULL){
    log_warn(LD_OR, "safe_or_conn->tls is NULL");
  } else {
    rv = tor_tls_export_key_material(safe_or_conn->tls, secrets_out,
                                     context, context_len, label);
  }

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
  return rv;
}

void
safe_or_connection_refill_buckets(safe_or_connection_t *safe_or_conn,
                                  uint32_t now_ts)
{
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);
  tor_assert(&safe_or_conn->bucket != NULL);

  token_bucket_rw_refill(&safe_or_conn->bucket, now_ts);
  safe_or_connection_refresh_bucket_rw_states(safe_or_conn);

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
}

// TODO: this might be better implemented as a message so that we don't need
//       to wait for the lock (but would require us to add a listener to the
//       safe conn)
void
safe_or_connection_adjust_buckets(safe_or_connection_t *safe_or_conn,
                                  uint32_t rate, uint32_t burst,
                                  bool reset, uint32_t now_ts)
{
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);
  tor_assert(&safe_or_conn->bucket != NULL);

  token_bucket_rw_adjust(&safe_or_conn->bucket, rate, burst);
  if (reset) {
    token_bucket_rw_reset(&safe_or_conn->bucket, now_ts);
    safe_or_connection_refresh_bucket_rw_states(safe_or_conn);
  }

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
}

static void
safe_or_connection_decrement_buckets(safe_or_connection_t *safe_or_conn,
                                     size_t num_read, size_t num_written,
                                     bool use_conn_buckets)
{
  if (use_conn_buckets) {
    token_bucket_rw_dec(&safe_or_conn->bucket, num_read, num_written);
  }
  safe_or_connection_refresh_bucket_rw_states(safe_or_conn);
}

static size_t
safe_or_connection_max_bytes_can_read(safe_or_connection_t *safe_or_conn,
                                      bool use_conn_buckets)
{
  // this function may become more complicated if we add support for global
  // buckets in the future
  // note: that would be a bad way to do it, since instead we should borrow
  // some space from the global bucket, and then commit it once the read
  // is actually finished

  size_t cell_network_size = \
    get_cell_network_size(safe_or_conn->wide_circ_ids?1:0);
  size_t bucket_max = token_bucket_rw_get_read(&safe_or_conn->bucket);

  size_t rv = 1024*cell_network_size;
  // this is the x32 the limit that 'connection_bucket_get_share()' uses

  if (use_conn_buckets && rv > bucket_max) {
    rv = bucket_max;
  }

  return rv;
}

static size_t
safe_or_connection_max_bytes_can_write(safe_or_connection_t *safe_or_conn,
                                       bool use_conn_buckets)
{
  // this function may become more complicated if we add support for global
  // buckets in the future
  // note: that would be a bad way to do it, since instead we should borrow
  // some space from the global bucket, and then commit it once the write
  // is actually finished
  if (use_conn_buckets) {
    return token_bucket_rw_get_write(&safe_or_conn->bucket);
  } else {
    return SIZE_MAX;
  }
}

static bool
safe_or_connection_is_read_wanted(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(safe_conn);

  return socket_rw_state_get(&safe_or_conn->tls_read_wanted) ||
         (socket_rw_state_get(&safe_or_conn->tor_read_wanted) &&
          socket_rw_state_get(&safe_or_conn->bucket_read_allowed));
}

static bool
safe_or_connection_is_write_wanted(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(safe_conn);

  return socket_rw_state_get(&safe_or_conn->tls_write_wanted) ||
         (socket_rw_state_get(&safe_or_conn->tor_write_wanted) &&
          socket_rw_state_get(&safe_or_conn->bucket_write_allowed));
}

static tor_error_t
safe_or_connection_update_state(safe_or_connection_t *safe_or_conn,
                                or_conn_state_t new_state)
{
  if (new_state == safe_or_conn->state) {
    log_warn(LD_OR, "Trying to change to the current state (or_conn_state_t) "
                    "of %d", new_state);
  }

  if (safe_or_conn->state == SAFE_OR_CONN_STATE_CLOSED &&
      new_state != SAFE_OR_CONN_STATE_CLOSED) {
    log_warn(LD_OR, "Trying to change out of the CLOSED state "
                    "(or_conn_state_t) to %d", new_state);
    tor_assert(0);
  }

  event_data_t null_data = { .ptr = NULL };
  // this is used by several cases below

  switch (new_state) {
  case SAFE_OR_CONN_STATE_UNINITIALIZED:
    tor_assert_unreached();
    break;
  case SAFE_OR_CONN_STATE_NO_SOCKET:
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    break;
  case SAFE_OR_CONN_STATE_TCP_CONNECTING:
    // the socket was EINPROGRESS, so wait for the socket to become
    // writable
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    event_source_publish(TO_SAFE_CONN(safe_or_conn)->event_source,
                         safe_or_conn_tcp_connecting_ev,
                         null_data, NULL);
    break;
  case SAFE_OR_CONN_STATE_PROXY_HANDSHAKING:
    log_warn(LD_OR, "Relay connection proxy handshake state has not yet "
                    "been implemented");
    tor_assert(0);
    break;
  case SAFE_OR_CONN_STATE_TLS_HANDSHAKING:
  {
    // begin the handshake when either the socket is readable or
    // writable
    if (safe_or_conn->tls != NULL) {
      log_warn(LD_OR, "safe_or_conn->tls should not be set");
      return E_ERROR;
    }
    bool is_receiving = !safe_or_conn->is_outgoing;
    if (TO_SAFE_CONN(safe_or_conn)->socket == TOR_INVALID_SOCKET) {
      log_warn(LD_OR, "No socket was set yet");
      return E_ERROR;
    }
    safe_or_conn->tls = tor_tls_new(TO_SAFE_CONN(safe_or_conn)->socket,
                                    is_receiving);
    if (safe_or_conn->tls == NULL) {
      log_warn(LD_OR, "Could not create a new tor TLS object");
      return E_ERROR;
    }
    tor_tls_release_socket(safe_or_conn->tls);
    // we want to have control over closing the socket
    if (safe_or_conn->remote_address_str != NULL) {
      tor_tls_set_logged_address(safe_or_conn->tls,
                                 safe_or_conn->remote_address_str);
    }
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    event_source_publish(TO_SAFE_CONN(safe_or_conn)->event_source,
                         safe_or_conn_tls_handshaking_ev,
                         null_data, NULL);
    break;
  }
  case SAFE_OR_CONN_STATE_LINK_HANDSHAKING:
  {
    if (safe_or_conn->tls == NULL) {
      log_warn(LD_OR, "safe_or_conn->tls was not set");
      return E_ERROR;
    }

    socket_rw_state_set(&safe_or_conn->tor_read_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));

    link_handshaking_ev_data *handshake_data = \
      tor_malloc_zero(sizeof(link_handshaking_ev_data));
    handshake_data->tls_own_cert = tor_tls_get_own_cert(safe_or_conn->tls);
    handshake_data->tls_peer_cert = tor_tls_get_peer_cert(safe_or_conn->tls);

    event_data_t ev_data = { .ptr = handshake_data };
    event_source_publish(TO_SAFE_CONN(safe_or_conn)->event_source,
                         safe_or_conn_link_handshaking_ev,
                         ev_data, link_handshaking_ev_free);
    break;
  }
  case SAFE_OR_CONN_STATE_OPEN:
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    event_source_publish(TO_SAFE_CONN(safe_or_conn)->event_source,
                         safe_or_conn_open_ev, null_data, NULL);
    break;
  case SAFE_OR_CONN_STATE_CLOSED:
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    event_source_publish(TO_SAFE_CONN(safe_or_conn)->event_source,
                         safe_or_conn_closed_ev, null_data, NULL);
    if (safe_or_conn->tls != NULL) {
      tor_tls_free(safe_or_conn->tls);
      safe_or_conn->tls = NULL;
    }
    safe_connection_close_socket(TO_SAFE_CONN(safe_or_conn));
    break;
  default:
    log_warn(LD_OR, "Unexpected state");
    tor_assert(0);
    break;
  }

  log_debug(LD_OR, "Safe OR conn changed from state %d to state %d",
            safe_or_conn->state, new_state);
  safe_or_conn->state = new_state;

  return E_SUCCESS;
}

static tor_error_t
safe_or_connection_check_tcp_connection(safe_or_connection_t *safe_or_conn)
{
  tor_assert(safe_or_conn != NULL);

  int e;
  socklen_t len = (socklen_t)sizeof(e);

  if (getsockopt(TO_SAFE_CONN(safe_or_conn)->socket, SOL_SOCKET, SO_ERROR,
                 (void *)&e, &len) < 0) {
    log_warn(LD_BUG, "getsockopt() syscall failed");
    return E_ERROR;
  }

  if (e != 0) {
    // some sort of error, but maybe just inprogress still
    if (!ERRNO_IS_CONN_EINPROGRESS(e)) {
      log_info(LD_NET, "In-progress connect failed. Removing. (%s)",
               tor_socket_strerror(e));
      return E_ERROR;
    } else {
      // no change, see if next time is better
      return E_SUCCESS;
    }
  }

  // there was no error
  return safe_or_connection_update_state(safe_or_conn,
           SAFE_OR_CONN_STATE_TLS_HANDSHAKING);
}

static int
safe_or_connection_read_tls(safe_or_connection_t *safe_or_conn,
                            size_t suggested_bytes_to_read,
                            size_t *total_bytes_read)
{
  tor_assert(safe_or_conn != NULL);
  tor_assert(suggested_bytes_to_read > 0);
  *total_bytes_read = 0;

  {
    size_t bytes_read = 0;
    int tls_rv = buf_read_from_tls(TO_SAFE_CONN(safe_or_conn)->inbuf,
                                   safe_or_conn->tls,
                                   suggested_bytes_to_read,
                                   &bytes_read);
    *total_bytes_read += bytes_read;

    if (tls_rv != TOR_TLS_DONE) {
      return tls_rv;
    }
  }

  int pending_bytes_to_read = tor_tls_get_pending_bytes(safe_or_conn->tls);
  if (pending_bytes_to_read > 0) {
    size_t bytes_read = 0;
    int tls_rv = buf_read_from_tls(TO_SAFE_CONN(safe_or_conn)->inbuf,
                                   safe_or_conn->tls,
                                   pending_bytes_to_read,
                                   &bytes_read);
    if (PREDICT_LIKELY(SIZE_MAX-(*total_bytes_read) > bytes_read)) {
      *total_bytes_read += bytes_read;
    } else {
      *total_bytes_read = SIZE_MAX;
    }

    tor_assert(tls_rv != TOR_TLS_WANTREAD && tls_rv != TOR_TLS_WANTWRITE);
    // we don't expect either of these when reading pending bytes
    if (tls_rv != TOR_TLS_DONE) {
      return tls_rv;
    }
  }

  return TOR_TLS_DONE;
}

static int
safe_or_connection_write_tls(safe_or_connection_t *safe_or_conn,
                             size_t max_bytes_to_write,
                             size_t *total_bytes_written)
{
  tor_assert(safe_or_conn != NULL);
  tor_assert(max_bytes_to_write > 0);
  *total_bytes_written = 0;

  size_t bytes_written = 0;
  int tls_rv = buf_flush_to_tls(TO_SAFE_CONN(safe_or_conn)->outbuf,
                                safe_or_conn->tls,
                                max_bytes_to_write,
                                &bytes_written);
  *total_bytes_written += bytes_written;

  return tls_rv;
}

// this function will be needed when proxies are supported
/*
static tor_error_t
safe_or_connection_read_plaintext(safe_or_connection_t *safe_or_conn)
{
  tor_assert(safe_or_conn != NULL);

  uint32_t coarse_time = monotime_coarse_get_stamp();
  safe_or_connection_refill_buckets(safe_or_conn, coarse_time);

  size_t bytes_to_read = safe_or_connection_max_bytes_can_read(safe_or_conn);

  if (bytes_to_read == 0) {
    log_debug(LD_NET, "Read callback running, but not supposed to read bytes.");
    return E_SUCCESS;
  }

  size_t buf_initial_size = buf_datalen(TO_SAFE_CONN(safe_or_conn)->inbuf);
  size_t bytes_read = 0;
  int reached_eof = 0;
  int socket_error = 0;
  // STEVE: if reusing this with control connections, then need to wrap
  //        with 'CONN_LOG_PROTECT' (see connection.c,
  //        !connection_speaks_cells, !conn->linked_conn. )
  int rv = buf_read_from_socket(TO_SAFE_CONN(safe_or_conn)->inbuf,
                                TO_SAFE_CONN(safe_or_conn)->socket,
                                bytes_to_read, &reached_eof,
                                &socket_error);
  if (rv < 0) {
    log_debug(LD_NET, "OR plaintext connection closed on read error.");
    // TODO: need to send the socket_error back to the main thread
    return E_ERROR;
  } else if(rv == 0 && reached_eof != 0) {
    // close the connection normally
    log_debug(LD_NET, "OR plaintext connection closed on read eof.");
    // return an error so that the calling function will close it
    return E_ERROR;
  } else {
    bytes_read = rv;
  }

  if (PREDICT_LIKELY(bytes_read < SIZE_MAX)) {
    tor_assert(bytes_read == \
               buf_datalen(TO_SAFE_CONN(safe_or_conn)->inbuf)-buf_initial_size);
  } else {
    log_warn(LD_NET, "We read an unexpectedly large number of bytes: %zu "
                     ">= SIZE_MAX",
             bytes_read);
  }

  log_debug(LD_NET, "OR plaintext read of %zu", bytes_read);

  safe_or_connection_decrement_buckets(safe_or_conn, bytes_read, 0);
  return E_SUCCESS;
}
*/

static tor_error_t
safe_or_connection_read_encrypted(safe_or_connection_t *safe_or_conn,
                                  bool use_conn_buckets)
{
  tor_assert(safe_or_conn != NULL);

  monotime_coarse_t now;
  monotime_coarse_get(&now);
  safe_or_connection_refill_buckets(safe_or_conn, monotime_coarse_to_stamp(&now));

  size_t suggested_bytes_to_read = \
    safe_or_connection_max_bytes_can_read(safe_or_conn, use_conn_buckets);
  // we may read slightly more than this due to pending TLS bytes

  if (suggested_bytes_to_read == 0) {
    log_debug(LD_NET, "Read callback running, but not supposed to read bytes.");
    return E_SUCCESS;
  }

  size_t buf_initial_size = buf_datalen(TO_SAFE_CONN(safe_or_conn)->inbuf);
  size_t bytes_read = 0;
  int tls_rv = safe_or_connection_read_tls(safe_or_conn,
                                           suggested_bytes_to_read,
                                           &bytes_read);
  switch (tls_rv) {
  case TOR_TLS_CLOSE:
  case TOR_TLS_ERROR_IO:
    log_debug(LD_NET, "TLS connection closed %son read. Closing.",
              tls_rv == TOR_TLS_CLOSE ? "cleanly " : "");
    return E_ERROR;
  CASE_TOR_TLS_ERROR_ANY_NONIO:
    log_debug(LD_NET, "TLS error [%s]. Breaking.",
              tor_tls_err_to_string(tls_rv));
    return E_ERROR;
  case TOR_TLS_WANTWRITE:
    // we need to wait for the socket to become writable
    // before we can do another read
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    break;
  case TOR_TLS_WANTREAD:
    // we need to wait for the socket to become readable
    // again, then do another read
    break;
  default:
    break;
  }

  if (PREDICT_LIKELY(bytes_read < SIZE_MAX)) {
    size_t buf_len_diff = buf_datalen(TO_SAFE_CONN(safe_or_conn)->inbuf)-buf_initial_size;
    if (bytes_read != buf_len_diff) {
      log_warn(LD_OR, "Doesn't match! bytes_read: %zu, buf_len_diff: %zu",
               bytes_read, buf_len_diff);
      tor_assert_nonfatal_unreached_once();
    }
  } else {
    log_warn(LD_NET, "We read an unexpectedly large number of bytes: %zu "
                     ">= SIZE_MAX",
             bytes_read);
  }

  log_recv_bytes(bytes_read, &now);

  size_t tls_bytes_read = 0;
  size_t tls_bytes_written = 0;
  tor_tls_get_n_raw_bytes(safe_or_conn->tls, &tls_bytes_read,
                          &tls_bytes_written);
  log_debug(LD_NET, "After TLS read of %zu: %zu read, %zu written",
            bytes_read, tls_bytes_read, tls_bytes_written);

  safe_or_connection_decrement_buckets(safe_or_conn, tls_bytes_read,
                                       tls_bytes_written, use_conn_buckets);

  // TODO: if get_options()->TestingEnableConnBwEvent, increase conn stats?

  return E_SUCCESS;
}

static tor_error_t
safe_or_connection_write_encrypted(safe_or_connection_t *safe_or_conn,
                                   bool use_conn_buckets)
{
  tor_assert(safe_or_conn != NULL);

  monotime_coarse_t now;
  monotime_coarse_get(&now);
  safe_or_connection_refill_buckets(safe_or_conn, monotime_coarse_to_stamp(&now));

  size_t max_bytes_to_write = \
    safe_or_connection_max_bytes_can_write(safe_or_conn, use_conn_buckets);

  if (max_bytes_to_write == 0) {
    log_debug(LD_NET, "Write callback running, but not supposed to write bytes.");
    return E_SUCCESS;
  }

  size_t buf_initial_size = buf_datalen(TO_SAFE_CONN(safe_or_conn)->outbuf);
  size_t bytes_written = 0;
  max_bytes_to_write = MIN(max_bytes_to_write, buf_initial_size);
  int tls_rv = safe_or_connection_write_tls(safe_or_conn,
                                            max_bytes_to_write,
                                            &bytes_written);
  switch (tls_rv) {
  case TOR_TLS_CLOSE:
  case TOR_TLS_ERROR_IO:
    log_debug(LD_NET, "TLS connection closed %son write. Closing.",
              tls_rv == TOR_TLS_CLOSE ? "cleanly " : "");
    return E_ERROR;
  CASE_TOR_TLS_ERROR_ANY_NONIO:
    log_debug(LD_NET, "TLS error [%s]. Breaking.",
              tor_tls_err_to_string(tls_rv));
    return E_ERROR;
  case TOR_TLS_WANTWRITE:
    // we need to wait for the socket to become writable
    // again, then do another write
    break;
  case TOR_TLS_WANTREAD:
    // we need to wait for the socket to become readable
    // before we can do another write
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    break;
  default:
    break;
  }

  if (PREDICT_LIKELY(bytes_written < SIZE_MAX)) {
    size_t buf_len_diff = buf_initial_size-buf_datalen(TO_SAFE_CONN(safe_or_conn)->outbuf);
    if (bytes_written != buf_len_diff) {
      log_warn(LD_OR, "Doesn't match! bytes_written: %zu, buf_len_diff: %zu",
               bytes_written, buf_len_diff);
      tor_assert_nonfatal_unreached_once();
    }
  } else {
    log_warn(LD_NET, "We wrote an unexpectedly large number of bytes: %zu "
                     ">= SIZE_MAX",
             bytes_written);
  }

  log_sent_bytes(bytes_written, &now);

  // fixes a throughput problem in old versions of Windows
  // TODO: we should still include this, but needs to be moved here since it's
  //       currently static
  //update_send_buffer_size(TO_SAFE_CONN(safe_or_conn)->socket);

  if (buf_datalen(TO_SAFE_CONN(safe_or_conn)->outbuf) == 0) {
    // we have no more data to write
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
  }

  size_t tls_bytes_read = 0;
  size_t tls_bytes_written = 0;
  tor_tls_get_n_raw_bytes(safe_or_conn->tls, &tls_bytes_read,
                          &tls_bytes_written);
  log_debug(LD_NET, "After TLS write of %zu: %zu read, %zu written",
            bytes_written, tls_bytes_read, tls_bytes_written);

  safe_or_connection_decrement_buckets(safe_or_conn, tls_bytes_read,
                                       tls_bytes_written, use_conn_buckets);

  // TODO: if get_options()->TestingEnableConnBwEvent, increase conn stats?

  return E_SUCCESS;
}

static tor_error_t
safe_or_connection_tls_handshake(safe_or_connection_t *safe_or_conn)
{
  tor_assert(safe_or_conn != NULL);
  check_no_tls_errors();

  int result = tor_tls_handshake(safe_or_conn->tls);
  
  switch (result) {
  CASE_TOR_TLS_ERROR_ANY:
    log_info(LD_OR, "TLS error [%s]",
             tor_tls_err_to_string(result));
    return E_ERROR;
  case TOR_TLS_CLOSE:
    log_info(LD_OR, "TLS closed");
    return E_ERROR;
  case TOR_TLS_WANTWRITE:
    // we need to wait for the socket to become writable
    // before we can continue the handshake
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    return E_SUCCESS;
  case TOR_TLS_WANTREAD:
    // we need to wait for the socket to become readable
    // before we can continue the handshake
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    return E_SUCCESS;
  case TOR_TLS_DONE:
    // the TLS handshake has finished, but not the entire link handshake
    if (tor_tls_is_server(safe_or_conn->tls)) {
      // we didn't start the handshake, so prepare for a v3 handshake
      log_debug(LD_OR, "Done with initial SSL handshake (receiver-side)");
    } else {
      // we need to start the v3 handshake
      log_debug(LD_OR, "Done with initial SSL handshake (initiator-side)");
      //if (connection_or_launch_v3_or_handshake(conn) < 0) {
      //  return E_ERROR;
      //}
    }
    return safe_or_connection_update_state(safe_or_conn,
             SAFE_OR_CONN_STATE_LINK_HANDSHAKING);
  default:
    log_warn(LD_OR, "Unexpected return value from handshake");
    return E_ERROR;
  }
}

/*
static int
safe_or_connection_tls_finish_v1_handshake(safe_or_connection_t *safe_or_conn)
{
  tor_assert(safe_or_conn != NULL);
  tor_assert(tor_tls_used_v1_handshake(safe_or_conn->tls));
  tor_assert(tor_tls_is_server(safe_or_conn->tls));
  tor_assert(!safe_or_conn->is_outgoing);
  // we should not be making v1 handshakes, but we may receive v1 handshakes

  log_debug(LD_HANDSHAKE, "%s tls v1 handshake on %p with %s done, using "
                          "ciphersuite %s. verifying.",
            safe_or_conn->is_outgoing?"Outgoing":"Incoming",
            safe_or_conn,
            safe_or_conn->remote_address_str,
            tor_tls_get_ciphersuite_name(safe_or_conn->tls));

  //tor_tls_block_renegotiation(safe_or_conn->tls);

  char digest_rcvd[DIGEST_LEN] = {0};
  // TODO fix below
  if (connection_or_check_valid_tls_handshake(conn, started_here,
                                              digest_rcvd) < 0) {
    return -1;
  }

  // TODO in main thread
  //circuit_build_times_network_is_live(get_circuit_build_times_mutable());
  //conn->link_proto = 1;
  //connection_or_init_conn_from_address(conn, &conn->base_.addr,
  //                                     conn->base_.port, digest_rcvd,
  //                                     NULL, 0);
  //rep_hist_note_negotiated_link_proto(1, started_here);
  //return connection_or_set_state_open(conn);

  return 0;
}
*/

static void
safe_or_connection_read_cb(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(safe_conn);

  log_debug(LD_OR, "OR connection read cb  (state=%d, obj=%p, %s)",
            safe_or_conn->state, safe_or_conn,
            safe_or_conn->is_outgoing?"outgoing":"incoming");

  //if (safe_or_conn->tls_write_waiting_on_socket_readable) {
  //  // since the socket is now readable, we can re-enable TLS write again
  //  safe_or_conn->tls_write_waiting_on_socket_readable = false;
  //  safe_connection_set_write_state(TO_SAFE_CONN(safe_or_conn), true);
  //}

  switch (safe_or_conn->state) {
  case SAFE_OR_CONN_STATE_UNINITIALIZED:
    tor_assert_unreached();
    break;
  case SAFE_OR_CONN_STATE_TCP_CONNECTING:
    // we shouldn't get here, so make sure we're not wanting to read
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    log_warn(LD_OR, "Connecting OR conection wants to read");
    break;
  case SAFE_OR_CONN_STATE_PROXY_HANDSHAKING:
    log_warn(LD_OR, "Relay connection proxy handshaking state has not yet "
                    "been implemented");
    tor_assert(0);
    // we are performing the proxy handshake
    //tor_error_t rv = safe_or_connection_plaintext(safe_or_conn);
    //if (rv != E_SUCCESS) {
    //  tor_assert(safe_or_connection_update_state(safe_or_conn,
    //    SAFE_OR_CONN_STATE_CLOSED) == E_SUCCESS);
    //}
    break;
  case SAFE_OR_CONN_STATE_TLS_HANDSHAKING:
  {
    // we are performing the initial TLS handshake
    tor_error_t rv = safe_or_connection_tls_handshake(safe_or_conn);
    if (rv != E_SUCCESS) {
      tor_assert(safe_or_connection_update_state(safe_or_conn,
        SAFE_OR_CONN_STATE_CLOSED) == E_SUCCESS);
    }
    break;
  }
  case SAFE_OR_CONN_STATE_LINK_HANDSHAKING:
  case SAFE_OR_CONN_STATE_OPEN:
  {
    // performing the link handshake, or the handshake has already
    // completed and we're sending/receiving cells
    if (socket_rw_state_get(&safe_or_conn->tls_read_wanted)) {
      // since the socket is now readable, we can re-enable writing again
      socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                          TO_SAFE_CONN(safe_or_conn));
      socket_rw_state_set(&safe_or_conn->tor_write_wanted, true,
                          TO_SAFE_CONN(safe_or_conn));
    }
    // TODO: we may not actually want to read here now that the states are
    // updated, should we re-check?

    //bool use_conn_buckets = (safe_or_conn->state == SAFE_OR_CONN_STATE_OPEN);
    bool use_conn_buckets = false;
    // TODO: still need to implement a timer event to refresh the token buckets

    tor_error_t rv = safe_or_connection_read_encrypted(safe_or_conn,
                                                       use_conn_buckets);
    if (rv != E_SUCCESS) {
      tor_assert(safe_or_connection_update_state(safe_or_conn,
        SAFE_OR_CONN_STATE_CLOSED) == E_SUCCESS);
    }

    if (!safe_or_conn->waiting_for_link_protocol) {
      process_cells_from_inbuf(safe_or_conn);
    }

    break;
  }
  case SAFE_OR_CONN_STATE_CLOSED:
  case SAFE_OR_CONN_STATE_NO_SOCKET:
    // we shouldn't get here, so make sure we're not wanting to read
    socket_rw_state_set(&safe_or_conn->tls_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_read_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    log_warn(LD_OR, "Closed OR conection wants to read");
    break;
  default:
    log_warn(LD_OR, "Unexpected safe OR connection state");
    tor_assert(0);
    break;
  }
}

static void
safe_or_connection_write_cb(safe_connection_t *safe_conn)
{
  tor_assert(safe_conn != NULL);
  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(safe_conn);

  log_debug(LD_OR, "OR connection write cb (state=%d, obj=%p, %s)",
            safe_or_conn->state, safe_or_conn,
            safe_or_conn->is_outgoing?"outgoing":"incoming");

  switch (safe_or_conn->state) {
  case SAFE_OR_CONN_STATE_UNINITIALIZED:
    tor_assert_unreached();
    break;
  case SAFE_OR_CONN_STATE_TCP_CONNECTING:
  {
    // the socket was connecting and is now ready to write, so we
    // should check for errors before using the socket
    tor_error_t rv = safe_or_connection_check_tcp_connection(safe_or_conn);
    if (rv != E_SUCCESS) {
      tor_assert(safe_or_connection_update_state(safe_or_conn,
        SAFE_OR_CONN_STATE_CLOSED) == E_SUCCESS);
    }
    break;
  }
  case SAFE_OR_CONN_STATE_PROXY_HANDSHAKING:
    log_warn(LD_OR, "Relay connection proxy handshaking state has not yet "
                    "been implemented");
    tor_assert(0);
    // we are performing the proxy handshake
    break;
  case SAFE_OR_CONN_STATE_TLS_HANDSHAKING:
  {
    // we are performing the initial TLS handshake
    tor_error_t rv = safe_or_connection_tls_handshake(safe_or_conn);
    if (rv != E_SUCCESS) {
      tor_assert(safe_or_connection_update_state(safe_or_conn,
        SAFE_OR_CONN_STATE_CLOSED) == E_SUCCESS);
    }
    break;
  }
  case SAFE_OR_CONN_STATE_LINK_HANDSHAKING:
  case SAFE_OR_CONN_STATE_OPEN:
  {
    // performing the link handshake, or the handshake has already
    // completed and we're sending/receiving cells
    if (socket_rw_state_get(&safe_or_conn->tls_write_wanted)) {
      // since the socket is now writable, we can re-enable reading again
      socket_rw_state_set(&safe_or_conn->tls_write_wanted, false,
                          TO_SAFE_CONN(safe_or_conn));
      socket_rw_state_set(&safe_or_conn->tor_read_wanted, true,
                          TO_SAFE_CONN(safe_or_conn));
    }
    // TODO: we may not actually want to write here now that the states are
    // updated, should we re-check?

    bool use_conn_buckets = (safe_or_conn->state == SAFE_OR_CONN_STATE_OPEN);

    tor_error_t rv = safe_or_connection_write_encrypted(safe_or_conn,
                                                        use_conn_buckets);
    if (rv != E_SUCCESS) {
      tor_assert(safe_or_connection_update_state(safe_or_conn,
        SAFE_OR_CONN_STATE_CLOSED) == E_SUCCESS);
    }
    break;
  }
  case SAFE_OR_CONN_STATE_CLOSED:
  case SAFE_OR_CONN_STATE_NO_SOCKET:
    // we shouldn't get here, so make sure we're not wanting to write
    socket_rw_state_set(&safe_or_conn->tls_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, false,
                        TO_SAFE_CONN(safe_or_conn));
    log_warn(LD_OR, "Closed OR conection wants to write");
    break;
  default:
    log_warn(LD_OR, "Unexpected safe OR connection state");
    tor_assert(0);
    break;
  }
}

/********************************************************/

/*
static void
append_to_incoming_cell_queue(safe_or_connection_t *safe_or_conn,
                              generic_cell_t *cell)
{
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&safe_or_conn->incoming_cell_queue->lock);

  TOR_TAILQ_INSERT_TAIL(&safe_or_conn->incoming_cell_queue->head, cell);

  tor_mutex_release(&safe_or_conn->incoming_cell_queue->lock);
}
*/

static void
safe_or_conn_outgoing_cell_cb(event_label_t label, event_data_t data,
                              void *context)
{
  safe_or_connection_t *safe_or_conn = TO_SAFE_OR_CONN(context);
  tor_assert(safe_or_conn != NULL);
  tor_mutex_acquire(&TO_SAFE_CONN(safe_or_conn)->lock);

  if (safe_or_conn->state == SAFE_OR_CONN_STATE_CLOSED) {
    tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
    return;
  }
  tor_assert(safe_or_conn->state == SAFE_OR_CONN_STATE_LINK_HANDSHAKING ||
             safe_or_conn->state == SAFE_OR_CONN_STATE_OPEN);

  struct buf_t *outbuf = TO_SAFE_CONN(safe_or_conn)->outbuf;
  int rv = -1;

  if (label == or_conn_outgoing_packed_cell) {
    packed_cell_t *packed_cell = data.ptr;
    tor_assert(packed_cell != NULL);
    size_t cell_network_size = \
      get_cell_network_size(safe_or_conn->wide_circ_ids?1:0);
    tor_assert(packed_cell_get_command(packed_cell,
      safe_or_conn->wide_circ_ids?1:0) != 0);

    rv = buf_add(outbuf, packed_cell->body, cell_network_size);
  } else if (label == or_conn_outgoing_fixed_cell) {
    cell_t *cell = data.ptr;
    tor_assert(cell != NULL);
    //tor_assert(cell->command != 0); // PADDING cells have command == 0
    size_t cell_network_size = \
      get_cell_network_size(safe_or_conn->wide_circ_ids?1:0);

    packed_cell_t packed_cell;
    cell_pack(&packed_cell, cell, safe_or_conn->wide_circ_ids?1:0);

    rv = buf_add(outbuf, packed_cell.body, cell_network_size);
  } else if (label == or_conn_outgoing_variable_cell) {
    var_cell_t *var_cell = data.ptr;
    tor_assert(var_cell != NULL);
    tor_assert(var_cell->command != 0);
    char header[VAR_CELL_MAX_HEADER_SIZE];
    int header_len = var_cell_pack_header(var_cell, header,
                                          safe_or_conn->wide_circ_ids?1:0);
    rv = buf_add(outbuf, header, header_len);
    if (rv >= 0) {
      rv = buf_add(outbuf, (char *)var_cell->payload, var_cell->payload_len);
    }
  } else {
    log_warn(LD_OR, "Received an unexpected event type");
    tor_assert_nonfatal_unreached_once();
  }

  if (rv < 0) {
    log_warn(LD_OR, "Safe OR connection could not write to outgoing buffer");
    tor_assert(safe_or_connection_update_state(safe_or_conn,
      SAFE_OR_CONN_STATE_CLOSED) == E_SUCCESS);
  } else {
    socket_rw_state_set(&safe_or_conn->tor_write_wanted, true,
                        TO_SAFE_CONN(safe_or_conn));
  }

  tor_mutex_release(&TO_SAFE_CONN(safe_or_conn)->lock);
}

static bool
fetch_cell(safe_or_connection_t *safe_or_conn, char *cell_buf)
{
  safe_connection_t *safe_conn = TO_SAFE_CONN(safe_or_conn);

  size_t cell_network_size = \
    get_cell_network_size(safe_or_conn->wide_circ_ids?1:0);

  if (buf_datalen(safe_conn->inbuf) < cell_network_size) {
    // don't have a full cell
    return false;
  }

  buf_get_bytes(safe_conn->inbuf, cell_buf, cell_network_size);
  safe_connection_inbuf_modified(safe_conn);

  return true;
}

static bool
fetch_var_cell(safe_or_connection_t *safe_or_conn, var_cell_t **var_cell_ptr)
{
  safe_connection_t *safe_conn = TO_SAFE_CONN(safe_or_conn);

  int link_protocol = safe_or_conn->link_protocol;
  *var_cell_ptr = NULL;
  int found_var_cell = fetch_var_cell_from_buf(safe_conn->inbuf, var_cell_ptr,
                                               link_protocol);
  if (*var_cell_ptr != NULL) {
    // there was not a *full* cell
    safe_connection_inbuf_modified(safe_conn);
  }
  return (found_var_cell != 0);
}

static void
void_var_cell_free(void *void_var_cell)
{
  var_cell_free_((var_cell_t *)void_var_cell);
}

static void
process_cells_from_inbuf(safe_or_connection_t *safe_or_conn)
{
  tor_assert(safe_or_conn != NULL);
  tor_assert(safe_or_conn->waiting_for_link_protocol == false);

  bool found_var_cell = false;
  bool found_fixed_cell = false;

  while (true) {
    var_cell_t *var_cell = NULL;
    bool next_is_var_cell = fetch_var_cell(safe_or_conn, &var_cell);

    if (next_is_var_cell) {
      if (var_cell == NULL) {
        // the next cell is a var cell, but it is not yet complete
        break;
      }

      found_var_cell = true;

      uint8_t command = var_cell->command;

      event_data_t event_data = { .ptr = var_cell };
      event_source_publish(TO_SAFE_CONN(safe_or_conn)->event_source,
                           safe_or_conn_var_cell_ev, event_data,
                           void_var_cell_free);

      // we no longer own the var cell at this point, so don't access it again

      if (safe_or_conn->link_protocol == 0 && command == CELL_VERSIONS) {
        // this is the first VERSIONS cell we've received;
        // in order to process future cells, we need to be told our
        // protocol version
        safe_or_conn->waiting_for_link_protocol = true;
        break;
      }
    } else {
      char buf[CELL_MAX_NETWORK_SIZE];
      bool next_is_fixed_cell = fetch_cell(safe_or_conn, buf);

      if (next_is_fixed_cell) {
        found_fixed_cell = true;

        // retrieve cell info from buf (create the host-order struct from the
        // network-order string)
        cell_t *cell = tor_malloc(sizeof(cell_t));
        cell_unpack(cell, buf, safe_or_conn->wide_circ_ids?1:0);

        event_data_t event_data = { .ptr = cell };
        event_source_publish(TO_SAFE_CONN(safe_or_conn)->event_source,
                             safe_or_conn_fixed_cell_ev, event_data,
                             tor_free_);

        // we no longer own the cell at this point, so don't access it again
      } else {
        // there is not yet a complete cell
        break;
      }
    }
  }

  if (found_var_cell) {
    event_source_wakeup_listener(TO_SAFE_CONN(safe_or_conn)->event_source,
                                 safe_or_conn_var_cell_ev);
  }
  if (found_fixed_cell) {
    event_source_wakeup_listener(TO_SAFE_CONN(safe_or_conn)->event_source,
                                 safe_or_conn_fixed_cell_ev);
  }
}
