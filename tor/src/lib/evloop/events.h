/* Copyright (c) 2013-2019, The Tor Project, Inc. */
/* See LICENSE for licensing information */

#ifndef EVLOOP_EVENTS_H
#define EVLOOP_EVENTS_H

#include "lib/lock/compat_mutex.h"
#include "lib/evloop/compat_libevent.h"
#include "lib/container/smartlist.h"
#include "ext/tor_queue.h"

/* The type of event. */
typedef int64_t event_label_t;

#define EVENT_LABEL_UNSET (-1)

/* Data provided with an event. */
typedef union event_data_t {
  void *ptr;
  uint64_t u64;
  uint16_t u16;
} event_data_t;

/* Object to hold an individual event and associated data. */
typedef struct event_wrapper_t {
  TOR_TAILQ_ENTRY(event_wrapper_t) next_event;
  event_label_t label;
  event_data_t data;
  void (*free_data_fn)(void *);
} event_wrapper_t;

/* A list of events and corresponding help strings. */
typedef struct event_registry_t {
  tor_mutex_t lock;
  smartlist_t *events;
} event_registry_t;

/* An object that publishes events to any subscribed listeners. */
typedef struct event_source_t {
  tor_mutex_t lock;
  smartlist_t *deliver_silently;
  smartlist_t *subscriptions;
} event_source_t;

/* An object that subscribes to a source and processes new events. */
typedef struct event_listener_t {
  tor_mutex_t lock;
  smartlist_t *callbacks;
  TOR_TAILQ_HEAD(pending_events_head_t, event_wrapper_t) pending_events;
  bool is_pending;
  struct event *eventloop_ev;
  void *context;
  int max_iterations;
} event_listener_t;

typedef void (*event_update_fn_t)(event_label_t,
                                  event_data_t *,
                                  event_data_t *);

typedef void (*process_event_fn_t)(event_label_t, event_data_t, void *);

/* Create the event registry. */
event_registry_t *event_registry_new(void);

/* Free the event registry. */
void event_registry_free(event_registry_t *registry);

/* Register a new event and optionally provide a string representation
   of the event label. */
event_label_t event_registry_register_event(event_registry_t *registry,
                                            const char *help_label);

/* Get the help label string registered for an event label. */
const char *event_registry_get_help_label(event_registry_t *registry,
                                          event_label_t event_label);

event_listener_t *event_listener_new(void *context);

void event_listener_free(event_listener_t *listener);

void event_listener_set_max_iterations(event_listener_t *listener,
                                       int max_iterations);

void event_listener_attach(event_listener_t *listener, struct event_base *base);

void event_listener_detach(event_listener_t *listener);

void event_listener_set_callback(event_listener_t *listener, event_label_t label,
                                 event_update_fn_t update_fn,
                                 process_event_fn_t process_event_fn);

void event_listener_process(event_listener_t *listener);

/* Create the event source, which publishes events to listeners. */
event_source_t *event_source_new(void);

void event_source_free(event_source_t *source);

void event_source_subscribe(event_source_t *source, event_listener_t *listener,
                            event_label_t label);

void event_source_unsubscribe(event_source_t *source,
                              event_listener_t *listener,
                              event_label_t label);

void event_source_unsubscribe_all(event_source_t *source,
                                  event_listener_t *listener);

void event_source_publish(event_source_t *source, event_label_t label,
                          event_data_t data, void (*free_data_fn)(void *));

void event_source_deliver_silently(event_source_t *source, event_label_t label,
                                   bool deliver_silently);

void event_source_wakeup_listener(event_source_t *source, event_label_t label);

#endif
