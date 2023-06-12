/* Copyright (c) 2013-2019, The Tor Project, Inc. */
/* See LICENSE for licensing information */

#ifndef OR_SAFE_CONN_H
#define OR_SAFE_CONN_H

#include "core/or/relay.h"
#include "lib/evloop/compat_libevent.h"
#include "lib/evloop/events.h"
#include "lib/evloop/token_bucket.h"
#include "lib/lock/compat_mutex.h"
#include "lib/tls/x509.h"

extern event_label_t safe_or_conn_tcp_connecting_ev;
extern event_label_t safe_or_conn_tls_handshaking_ev;
extern event_label_t safe_or_conn_link_handshaking_ev;
extern event_label_t safe_or_conn_open_ev;
extern event_label_t safe_or_conn_closed_ev;
extern event_label_t safe_or_conn_fixed_cell_ev;
extern event_label_t safe_or_conn_var_cell_ev;

typedef struct link_handshaking_ev_data_t {
  tor_x509_cert_t *tls_own_cert; // the ownership is passed in this event
  tor_x509_cert_t *tls_peer_cert; // the ownership is passed in this event
} link_handshaking_ev_data;

void link_handshaking_ev_free(void *ptr);

/*
typedef struct generic_cell_t {
  TOR_SIMPLEQ_ENTRY(safe_cell_t) next;
  enum {
    CELL_TYPE_FIXED,
    CELL_TYPE_VAR,
  } type;
  union {
    cell_t *fixed_cell;
    var_cell_t *var_cell;
  } data;
} generic_cell_t;

typedef struct safe_cell_queue_t {
  tor_mutex_t lock;
  TOR_SIMPLEQ_HEAD(safe_cell_queue_head_t, generic_cell_t) head;
} safe_cell_queue_t;
*/

//#define SAFE_BASE_CONN_MAGIC 0x64DB4EE2u
#define SAFE_OR_CONN_MAGIC 0x1221ABBAu

typedef enum tor_error_t {
  E_SUCCESS = 0,
  E_ERROR = 1,
} tor_error_t;

typedef enum or_conn_state_t {
  SAFE_OR_CONN_STATE_UNINITIALIZED,
  SAFE_OR_CONN_STATE_NO_SOCKET,
  SAFE_OR_CONN_STATE_TCP_CONNECTING,
  SAFE_OR_CONN_STATE_PROXY_HANDSHAKING,
  SAFE_OR_CONN_STATE_TLS_HANDSHAKING,
  SAFE_OR_CONN_STATE_LINK_HANDSHAKING,
  SAFE_OR_CONN_STATE_OPEN,
  SAFE_OR_CONN_STATE_CLOSED,
} or_conn_state_t;

typedef struct socket_rw_state_t {
  bool state;
} socket_rw_state_t;

typedef struct safe_connection_t {
  uint32_t magic;
  tor_mutex_t lock;

  bool linked;
  tor_socket_t socket;

  struct event *read_event;
  struct event *write_event;
  socket_rw_state_t read_allowed;
  socket_rw_state_t write_allowed;

  bool (*is_read_wanted)(struct safe_connection_t *);
  bool (*is_write_wanted)(struct safe_connection_t *);
  void (*read_cb)(struct safe_connection_t *);
  void (*write_cb)(struct safe_connection_t *);
  void (*socket_added_cb)(struct safe_connection_t *);
  void (*inbuf_modified_cb)(struct safe_connection_t *);
  void (*outbuf_modified_cb)(struct safe_connection_t *);

  struct buf_t *inbuf;
  struct buf_t *outbuf;

  event_source_t *event_source;
  event_listener_t *event_listener;
  bool care_about_modified;
} safe_connection_t;

typedef struct safe_or_connection_t {
  safe_connection_t base_;
  token_bucket_rw_t bucket;
  struct tor_tls_t *tls;
  or_conn_state_t state;
  bool is_outgoing;
  char *remote_address_str;

  uint16_t link_protocol;
  bool wide_circ_ids;
  bool waiting_for_link_protocol;

  //safe_cell_queue_t incoming_cell_queue;

  socket_rw_state_t tor_read_wanted;
  socket_rw_state_t tor_write_wanted;
  socket_rw_state_t tls_read_wanted;
  socket_rw_state_t tls_write_wanted;
  socket_rw_state_t bucket_read_allowed;
  socket_rw_state_t bucket_write_allowed;

  //bool tls_read_waiting_on_socket_writable;
  //bool tls_write_waiting_on_socket_readable;
} safe_or_connection_t;

safe_or_connection_t *TO_SAFE_OR_CONN(safe_connection_t *safe_conn);

#define TO_SAFE_CONN(c) (&(((c)->base_)))

void safe_or_conn_register_events(event_registry_t *registry);

void safe_or_conn_buf_data_event_update(event_label_t label,
                                        event_data_t *old_data,
                                        event_data_t *new_data);

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
                     bool requires_buffers, bool linked);

void
safe_connection_set_socket(safe_connection_t *safe_conn, tor_socket_t socket);

void
safe_connection_subscribe(safe_connection_t *safe_conn,
                          event_listener_t *listener, event_label_t label);

void
safe_connection_unsubscribe_all(safe_connection_t *safe_conn,
                                event_listener_t *listener);

void
safe_connection_unregister_events(safe_connection_t *safe_conn);

tor_error_t
safe_connection_register_events(safe_connection_t *safe_conn,
                                struct event_base *event_base);

void
safe_connection_set_read_permission(safe_connection_t *safe_conn,
                                    bool read_allowed);

void
safe_connection_set_write_permission(safe_connection_t *safe_conn,
                                     bool write_allowed);

void
safe_connection_start_caring_about_modified(safe_connection_t *safe_conn);

void
safe_connection_stop_caring_about_modified(safe_connection_t *safe_conn);

void
safe_connection_inbuf_modified(safe_connection_t *safe_conn);

void
safe_connection_outbuf_modified(safe_connection_t *safe_conn);

/********************************************************/

safe_or_connection_t *
safe_or_connection_new(bool requires_buffers, bool is_outgoing,
                       const char *remote_address_str,
                       event_source_t *conn_event_source);

void
safe_or_connection_get_tls_desc(safe_or_connection_t *safe_or_conn,
                                char *buf, size_t buf_size);

int
safe_or_connection_tls_secrets(safe_or_connection_t *safe_or_conn,
                               uint8_t *secrets_out);

int
safe_or_connection_key_material(safe_or_connection_t *safe_or_conn,
                                uint8_t *secrets_out,
                                const uint8_t *context,
                                size_t context_len, const char *label);

void
safe_or_connection_refill_buckets(safe_or_connection_t *safe_or_conn,
                                  uint32_t now_ts);

void
safe_or_connection_adjust_buckets(safe_or_connection_t *safe_or_conn,
                                  uint32_t rate, uint32_t burst,
                                  bool reset, uint32_t now_ts);

#endif
