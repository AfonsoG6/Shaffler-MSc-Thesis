/* Copyright (c) 2013-2019, The Tor Project, Inc. */
/* See LICENSE for licensing information */

#include "lib/evloop/events.h"

#include "lib/log/util_bug.h"

#include <event2/util.h>
#include <event2/event.h>
#include <string.h>

/* An unsupported libevent function. */
void event_active_later_(struct event *, int);

/* How a subscribed listener wants to receive an event. */
typedef struct event_subscription_t {
  event_listener_t *listener;
} event_subscription_t;

/* What a listener should do if it receives an event. */
typedef struct event_callback_t {
  event_update_fn_t update_fn;
  process_event_fn_t process_event_fn;
} event_callback_t;

/**************************/

static event_subscription_t *
event_subscription_new(event_listener_t *listener)
{
  tor_assert(listener != NULL);
  event_subscription_t *sub = tor_malloc_zero(sizeof(event_subscription_t));
  sub->listener = listener;
  return sub;
}

static void
event_subscription_free(event_subscription_t *sub)
{
  tor_assert(sub != NULL);
  memset(sub, 0x00, sizeof(*sub));
  tor_free(sub);
}

/**************************/

static event_callback_t *
event_callback_new(event_update_fn_t update_fn,
                   process_event_fn_t process_event_fn)
{
  tor_assert(process_event_fn != NULL);
  event_callback_t *cb = tor_malloc_zero(sizeof(event_callback_t));
  cb->update_fn = update_fn;
  cb->process_event_fn = process_event_fn;
  return cb;
}

static void
event_callback_free(event_callback_t *cb)
{
  tor_assert(cb != NULL);
  memset(cb, 0x00, sizeof(*cb));
  tor_free(cb);
}

/**************************/

static event_wrapper_t *
event_wrapper_new(event_label_t label,
                  event_data_t data,
                  void (*free_data_fn)(void *))
{
  event_wrapper_t *wrapper = tor_malloc_zero(sizeof(event_wrapper_t));
  wrapper->label = label;
  wrapper->data = data;
  wrapper->free_data_fn = free_data_fn;
  return wrapper;
}

static void
event_wrapper_free(event_wrapper_t *wrapper)
{
  tor_assert(wrapper != NULL);
  if (wrapper->free_data_fn != NULL) {
    wrapper->free_data_fn(wrapper->data.ptr);
  }
  memset(wrapper, 0x00, sizeof(*wrapper));
  tor_free(wrapper);
}

/**************************/

event_registry_t *
event_registry_new(void)
{
  event_registry_t* registry = tor_malloc_zero(sizeof(event_registry_t));

  tor_mutex_init(&registry->lock);
  registry->events = smartlist_new();

  return registry;
}

void
event_registry_free(event_registry_t *registry)
{
  tor_assert(registry != NULL);

  tor_mutex_uninit(&registry->lock);

  SMARTLIST_FOREACH_BEGIN(registry->events, char *, help_label) {
    if (help_label != NULL) {
      tor_free(help_label);
    }
  } SMARTLIST_FOREACH_END(help_label);
  smartlist_free(registry->events);

  memset(registry, 0x00, sizeof(*registry));
  tor_free(registry);
}

event_label_t
event_registry_register_event(event_registry_t *registry,
                              const char *help_label)
{
  tor_assert(registry != NULL);
  tor_mutex_acquire(&registry->lock);

  int num_events = smartlist_len(registry->events);
  if (help_label) {
    smartlist_add_strdup(registry->events, help_label);
  } else {
    smartlist_add(registry->events, NULL);
  }

  tor_mutex_release(&registry->lock);
  return (event_label_t)num_events;
}

const char *
event_registry_get_help_label(event_registry_t *registry,
                              event_label_t event_label)
{
  tor_assert(registry != NULL);
  tor_mutex_acquire(&registry->lock);

  int label_index = (int)event_label;
  tor_assert(label_index >= 0);
  const char *help_label = smartlist_get(registry->events,
                                         label_index);

  tor_mutex_release(&registry->lock);
  return help_label;
}

/**************************/

static void
event_listener_eventloop_cb(evutil_socket_t sock, short events, void *arg)
{
  event_listener_t *listener = arg;
  (void) sock;
  (void) events;
  event_listener_process(listener);
}

event_listener_t *
event_listener_new(void *context)
{
  event_listener_t* listener = tor_malloc_zero(sizeof(event_listener_t));

  tor_mutex_init(&listener->lock);
  listener->is_pending = false;
  listener->callbacks = smartlist_new();
  TOR_TAILQ_INIT(&listener->pending_events);
  listener->context = context;
  listener->eventloop_ev = NULL;
  listener->max_iterations = -1;

  return listener;
}

void
event_listener_free(event_listener_t *listener)
{
  tor_assert(listener != NULL);

  tor_mutex_acquire(&listener->lock);

  if (listener->eventloop_ev != NULL) {
    event_listener_detach(listener);
    // this will make sure the libevent callback has stopped
  }

  while (!TOR_TAILQ_EMPTY(&listener->pending_events)) {
    event_wrapper_t *wrapper = TOR_TAILQ_FIRST(&listener->pending_events);
    TOR_TAILQ_REMOVE(&listener->pending_events, wrapper, next_event);
    event_wrapper_free(wrapper);
  }

  SMARTLIST_FOREACH_BEGIN(listener->callbacks, event_callback_t *, cb) {
    if (cb != NULL) {
      event_callback_free(cb);
    }
  } SMARTLIST_FOREACH_END(cb);
  smartlist_free(listener->callbacks);

  listener->context = NULL;
  listener->is_pending = false;

  tor_mutex_release(&listener->lock);
  tor_mutex_uninit(&listener->lock);

  memset(listener, 0x00, sizeof(*listener));
  tor_free(listener);
}

void
event_listener_set_max_iterations(event_listener_t *listener, int max_iterations)
{
  tor_assert(listener != NULL);

  tor_mutex_acquire(&listener->lock);

  listener->max_iterations = max_iterations;

  tor_mutex_release(&listener->lock);
}

void
event_listener_attach(event_listener_t *listener, struct event_base *base)
{
  tor_assert(listener != NULL);
  tor_assert(base != NULL);

  tor_mutex_acquire(&listener->lock);

  tor_assert(listener->eventloop_ev == NULL);
  listener->eventloop_ev = tor_event_new(base, -1,
                                         EV_READ|EV_PERSIST, // TODO: do we need persist?
                                         event_listener_eventloop_cb,
                                         listener);

  if (listener->is_pending) {
    event_active(listener->eventloop_ev, EV_READ, 1);
  }

  tor_mutex_release(&listener->lock);
}

void
event_listener_detach(event_listener_t *listener)
{
  tor_assert(listener != NULL);

  tor_mutex_acquire(&listener->lock);

  if (listener->eventloop_ev != NULL) {
    tor_event_free(listener->eventloop_ev);
    listener->eventloop_ev = NULL;
  }

  tor_mutex_release(&listener->lock);
}

void
event_listener_set_callback(event_listener_t *listener, event_label_t label,
                            event_update_fn_t update_fn,
                            process_event_fn_t process_event_fn)
{
  tor_assert(listener != NULL);
  tor_assert(label != EVENT_LABEL_UNSET);
  tor_assert(process_event_fn != NULL);
  
  int index = (int)label;
  tor_assert(index >= 0);

  event_callback_t *cb = event_callback_new(update_fn, process_event_fn);

  if (index >= 1000) {
    log_warn(LD_BUG, "An event label was very large (%d), but the event "
                     "listener assumes that event labels are small.", index);
    /* We're using a smartlist as a lookup table, and assume that the labels are
       small and therefore the list should not be sparse. If the label is large,
       then we either have *many* events, or we're choosing our event labels
       inefficiently. */
  }

  tor_mutex_acquire(&listener->lock);

  smartlist_grow(listener->callbacks, index+1);

  event_callback_t *existing_cb = smartlist_get(listener->callbacks, index);
  if (existing_cb != NULL) {
    // we only support one callback per event type
    event_callback_free(existing_cb);
    log_warn(LD_BUG, "We are overriding a previous callback.");
  }
  smartlist_set(listener->callbacks, index, cb);

  tor_mutex_release(&listener->lock); 
}

static void
event_listener_receive(event_listener_t *listener, event_label_t label,
                       event_wrapper_t *wrapper, bool notify)
{
  tor_assert(listener != NULL);
  tor_assert(label != EVENT_LABEL_UNSET);

  int index = (int)label;
  tor_assert(index >= 0);

  tor_mutex_acquire(&listener->lock);

  if (index >= smartlist_len(listener->callbacks)) {
    log_warn(LD_BUG, "We don't have a callback for this event");
    if (wrapper != NULL) {
      event_wrapper_free(wrapper);
    }
    tor_mutex_release(&listener->lock);
    return;
  }

  event_callback_t *cb = smartlist_get(listener->callbacks, index);
  if (cb == NULL) {
    log_warn(LD_BUG, "We don't have a callback for this event");
    if (wrapper != NULL) {
      event_wrapper_free(wrapper);
    }
    tor_mutex_release(&listener->lock);
    return;
  }

  event_wrapper_t *last = TOR_TAILQ_LAST(&listener->pending_events,
                                         pending_events_head_t);
  if (cb->update_fn != NULL && last != NULL && last->label == label) {
    // the last added event was of the same type and we set an update function,
    // so we should update the last event rather than adding a new one
    cb->update_fn(label, &last->data, &wrapper->data);
    if (wrapper != NULL) {
      event_wrapper_free(wrapper);
    }
  } else {
    tor_assert(wrapper != NULL);
    TOR_TAILQ_INSERT_TAIL(&listener->pending_events, wrapper, next_event);
  }

  if (!listener->is_pending && notify) {
    listener->is_pending = true;
    if (listener->eventloop_ev != NULL) {
      event_active_later_(listener->eventloop_ev, EV_READ);
    }
  }

  tor_mutex_release(&listener->lock);
}

static void
event_listener_wakeup(event_listener_t *listener)
{
  tor_assert(listener != NULL);
  tor_mutex_acquire(&listener->lock);

  if (!listener->is_pending && !TOR_TAILQ_EMPTY(&listener->pending_events)) {
    // not pending but have waiting events
    listener->is_pending = true;
    if (listener->eventloop_ev != NULL) {
      event_active_later_(listener->eventloop_ev, EV_READ);
    }
  }

  tor_mutex_release(&listener->lock);
}

void
event_listener_process(event_listener_t *listener)
{
  tor_assert(listener != NULL);

  int counter = 0;

  tor_mutex_acquire(&listener->lock);

  void *context = listener->context;
  int max_iterations = listener->max_iterations;

  while (!TOR_TAILQ_EMPTY(&listener->pending_events) &&
         (max_iterations < 0 || counter < max_iterations)) {
    event_wrapper_t *wrapper = TOR_TAILQ_FIRST(&listener->pending_events);
    TOR_TAILQ_REMOVE(&listener->pending_events, wrapper, next_event);
    tor_assert(wrapper != NULL);

    process_event_fn_t process_event_fn = NULL;
    int index = (int)wrapper->label;

    // do we have a callback for this event label?
    if (PREDICT_LIKELY(index < smartlist_len(listener->callbacks))) {
      event_callback_t *cb = smartlist_get(listener->callbacks, index);
      if (cb != NULL) {
        process_event_fn = cb->process_event_fn;
      }
    }

    tor_mutex_release(&listener->lock);

    if (PREDICT_LIKELY(process_event_fn != NULL)) {
      process_event_fn(wrapper->label, wrapper->data, context);
      counter += 1;
      // only increase the counter if a callback was run
    } else {
      // no callback available
      log_warn(LD_BUG, "An event was received but had no callback");
    }

    event_wrapper_free(wrapper);
    tor_mutex_acquire(&listener->lock);
  }

  if (TOR_TAILQ_EMPTY(&listener->pending_events)) {
    listener->is_pending = false;
  } else {
    event_active_later_(listener->eventloop_ev, EV_READ);
  }

  tor_mutex_release(&listener->lock);
}

/**************************/

event_source_t *
event_source_new(void)
{
  event_source_t* source = tor_malloc_zero(sizeof(event_source_t));
  tor_mutex_init(&source->lock);
  source->deliver_silently = smartlist_new();
  source->subscriptions = smartlist_new();

  return source;
}

void
event_source_free(event_source_t *source)
{
  tor_assert(source != NULL);

  tor_mutex_uninit(&source->lock);

  SMARTLIST_FOREACH_BEGIN(source->subscriptions, event_subscription_t *, sub) {
    if (sub != NULL) {
      event_subscription_free(sub);
    }
  } SMARTLIST_FOREACH_END(sub);
  smartlist_free(source->subscriptions);
  smartlist_free(source->deliver_silently);

  memset(source, 0x00, sizeof(*source));
  tor_free(source);
}

void
event_source_subscribe(event_source_t *source, event_listener_t *listener,
                       event_label_t label)
{
  tor_assert(source != NULL);
  tor_assert(listener != NULL);
  tor_assert(label != EVENT_LABEL_UNSET);

  int index = (int)label;
  tor_assert(index >= 0);

  if (index >= 1000) {
    log_warn(LD_BUG, "An event label was very large (%d), but the event source "
                     "assumes that event labels are small.", index);
    /* We're using a smartlist as a lookup table, and assume that the labels are
       small and therefore the list should not be sparse. If the label is large,
       then we either have *many* events, or we're choosing our event labels
       inefficiently. */
  }

  event_subscription_t *sub = event_subscription_new(listener);

  tor_mutex_acquire(&source->lock);

  smartlist_grow(source->subscriptions, index+1);

  event_subscription_t *existing_sub = smartlist_get(source->subscriptions, index);
  if (existing_sub != NULL) {
    // we only support one listener per event type
    event_subscription_free(existing_sub);
    log_warn(LD_BUG, "We are overriding a previous listener.");
  }
  smartlist_set(source->subscriptions, index, sub);

  tor_mutex_release(&source->lock);
}

void
event_source_unsubscribe(event_source_t *source, event_listener_t *listener,
                         event_label_t label)
{
  tor_assert(source != NULL);
  tor_assert(listener != NULL);
  tor_assert(label != EVENT_LABEL_UNSET);

  int index = (int)label;
  tor_assert(index >= 0);

  tor_mutex_acquire(&source->lock);

  if (index >= smartlist_len(source->subscriptions)) {
    // there are no subscribers for this event
    log_warn(LD_GENERAL, "Listener wanted to unsubscribe, but was not subscribed.");
    tor_mutex_release(&source->lock);
    return;
  }

  event_subscription_t *current_sub = smartlist_get(source->subscriptions, index);
  if (current_sub == NULL || current_sub->listener != listener) {
    log_warn(LD_GENERAL, "Listener wanted to unsubscribe, but was not subscribed.");
    tor_mutex_release(&source->lock);
    return;
  }

  smartlist_set(source->subscriptions, index, NULL);
  event_subscription_free(current_sub);

  tor_mutex_release(&source->lock);
}

void
event_source_unsubscribe_all(event_source_t *source, event_listener_t *listener)
{
  tor_assert(source != NULL);
  tor_assert(listener != NULL);

  tor_mutex_acquire(&source->lock);

  SMARTLIST_FOREACH_BEGIN(source->subscriptions, event_subscription_t *, sub) {
    if (sub != NULL && sub->listener == listener) {
      event_subscription_free(sub);
      SMARTLIST_REPLACE_CURRENT(source->subscriptions, sub, NULL);
    }
  } SMARTLIST_FOREACH_END(sub);

  tor_mutex_release(&source->lock);
}

void
event_source_publish(event_source_t *source, event_label_t label,
                     event_data_t data, void (*free_data_fn)(void *))
{
  tor_assert(source != NULL);
  tor_assert(label != EVENT_LABEL_UNSET);

  int index = (int)label;
  tor_assert(index >= 0);

  tor_mutex_acquire(&source->lock);

  if (index >= smartlist_len(source->subscriptions)) {
    // there are no subscribers for this event
    tor_mutex_release(&source->lock);
    if (free_data_fn != NULL) {
      free_data_fn(data.ptr);
    }
    return;
  }

  event_subscription_t *sub = smartlist_get(source->subscriptions, index);
  if (sub == NULL || sub->listener == NULL) {
    // there are no subscribers for this event
    tor_mutex_release(&source->lock);
    if (free_data_fn != NULL) {
      free_data_fn(data.ptr);
    }
    return;
  }

  bool deliver_silently;
  if (index >= smartlist_len(source->deliver_silently)) {
    // default is to not deliver silently
    deliver_silently = false;
  } else {
    deliver_silently = (smartlist_get(source->deliver_silently, index) != 0);
  }

  event_wrapper_t *wrapper = NULL;
  wrapper = event_wrapper_new(label, data, free_data_fn);
  event_listener_receive(sub->listener, label, wrapper, !deliver_silently);

  tor_mutex_release(&source->lock);
}

void
event_source_deliver_silently(event_source_t *source, event_label_t label,
                              bool deliver_silently)
{
  tor_assert(source != NULL);
  tor_assert(label != EVENT_LABEL_UNSET);

  int index = (int)label;
  tor_assert(index >= 0);

  if (index >= 1000) {
    log_warn(LD_BUG, "An event label was very large (%d), but the event source "
                     "assumes that event labels are small.", index);
    /* We're using a smartlist as a lookup table, and assume that the labels are
       small and therefore the list should not be sparse. If the label is large,
       then we either have *many* events, or we're choosing our event labels
       inefficiently. */
  }

  tor_mutex_acquire(&source->lock);

  smartlist_grow(source->deliver_silently, index+1);
  // default is to not deliver silently
  smartlist_set(source->deliver_silently, index, (void *)deliver_silently);

  tor_mutex_release(&source->lock);
}

void
event_source_wakeup_listener(event_source_t *source, event_label_t label)
{
  tor_assert(source != NULL);
  tor_assert(label != EVENT_LABEL_UNSET);

  int index = (int)label;
  tor_assert(index >= 0);

  tor_mutex_acquire(&source->lock);

  if (index >= smartlist_len(source->subscriptions)) {
    // there are no subscribers for this event
    tor_mutex_release(&source->lock);
    return;
  }

  event_subscription_t *sub = smartlist_get(source->subscriptions, index);
  if (sub == NULL || sub->listener == NULL) {
    // there are no subscribers for this event
    tor_mutex_release(&source->lock);
    return;
  }

  event_listener_wakeup(sub->listener);

  tor_mutex_release(&source->lock);
}
