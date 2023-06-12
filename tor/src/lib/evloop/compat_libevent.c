/* Copyright (c) 2009-2019, The Tor Project, Inc. */
/* See LICENSE for licensing information */

/**
 * \file compat_libevent.c
 * \brief Wrappers and utility functions for Libevent.
 */

#include "orconfig.h"
#define COMPAT_LIBEVENT_PRIVATE
#include "lib/evloop/compat_libevent.h"

#include "lib/crypt_ops/crypto_rand.h"
#include "lib/log/log.h"
#include "lib/log/util_bug.h"
#include "lib/string/compat_string.h"

#include <event2/thread.h>
#include <string.h>

/** A string which, if it appears in a libevent log, should be ignored. */
static const char *suppress_msg = NULL;
/** Callback function passed to event_set_log() so we can intercept
 * log messages from libevent. */
STATIC void
libevent_logging_callback(int severity, const char *msg)
{
  char buf[1024];
  size_t n;
  if (suppress_msg && strstr(msg, suppress_msg))
    return;
  n = strlcpy(buf, msg, sizeof(buf));
  if (n && n < sizeof(buf) && buf[n-1] == '\n') {
    buf[n-1] = '\0';
  }
  switch (severity) {
    case _EVENT_LOG_DEBUG:
      log_debug(LD_NOCB|LD_NET, "Message from libevent: %s", buf);
      break;
    case _EVENT_LOG_MSG:
      log_info(LD_NOCB|LD_NET, "Message from libevent: %s", buf);
      break;
    case _EVENT_LOG_WARN:
      log_warn(LD_NOCB|LD_GENERAL, "Warning from libevent: %s", buf);
      break;
    case _EVENT_LOG_ERR:
      log_err(LD_NOCB|LD_GENERAL, "Error from libevent: %s", buf);
      break;
    default:
      log_warn(LD_NOCB|LD_GENERAL, "Message [%d] from libevent: %s",
          severity, buf);
      break;
  }
}
/** Set hook to intercept log messages from libevent. */
void
configure_libevent_logging(void)
{
  event_set_log_callback(libevent_logging_callback);
}

/** Ignore any libevent log message that contains <b>msg</b>. */
void
suppress_libevent_log_msg(const char *msg)
{
  suppress_msg = msg;
}

/* Wrapper for event_free() that tolerates tor_event_free(NULL) */
void
tor_event_free_(struct event *ev)
{
  if (ev == NULL)
    return;
  event_free(ev);
}

/** Global event bases for use by the eventloop threads. */
static tor_thread_t **threads = NULL;
static struct event_base **eventloops = NULL;
static tor_threadlocal_t eventloop_index;
static int num_eventloops = -1;

/**
 * @defgroup postloop post-loop event helpers
 *
 * If we're not careful, Libevent can susceptible to infinite event chains:
 * one event can activate another, whose callback activates another, whose
 * callback activates another, ad infinitum.  While this is happening,
 * Libevent won't be checking timeouts, socket-based events, signals, and so
 * on.
 *
 * We solve this problem by marking some events as "post-loop".  A post-loop
 * event behaves like any ordinary event, but any events that _it_ activates
 * cannot run until Libevent has checked for other events at least once.
 *
 * @{ */

/**
 * Events that stop Libevent from running any more events on the current
 * iteration of its loop, until it has re-checked for socket events, signal
 * events, timeouts, etc.
 */
struct event **rescan_eventloop_events = NULL;

/**
 * Callback to implement rescan_mainloop_ev: it simply exits the mainloop,
 * and relies on Tor to re-enter the mainloop since no error has occurred.
 */
static void
rescan_mainloop_cb(evutil_socket_t fd, short events, void *arg)
{
  (void)fd;
  (void)events;
  struct event_base *the_base = arg;
  event_base_loopbreak(the_base);
}

/** @} */

struct event_base *
get_eventloop(int index)
{
  tor_assert(index >= 0 && index < num_eventloops);
  tor_assert(eventloops != NULL);
  tor_assert(eventloops[index] != NULL);
  return eventloops[index];
}

int
get_local_eventloop_index(void) {
  int *index = tor_threadlocal_get(&eventloop_index);
  tor_assert(index != NULL);
  return *index;
}

int
get_num_eventloops(void)
{
  tor_assert(num_eventloops != -1);
  return num_eventloops;
}

/* Tell the eventloops to stop soon. */
void
rescan_eventloops(void)
{
  tor_assert(rescan_eventloop_events != NULL);
  for (int i=0; i<num_eventloops; i++) {
    tor_assert(rescan_eventloop_events[i] != NULL);
    event_active(rescan_eventloop_events[i], EV_READ, 1);
  }
}

/* This is what passes for version detection on OSX.  We set
 * MACOSX_KQUEUE_IS_BROKEN to true iff we're on a version of OSX before
 * 10.4.0 (aka 1040). */
#ifdef __APPLE__
#ifdef __ENVIRONMENT_MAC_OS_X_VERSION_MIN_REQUIRED__
#define MACOSX_KQUEUE_IS_BROKEN \
  (__ENVIRONMENT_MAC_OS_X_VERSION_MIN_REQUIRED__ < 1040)
#else
#define MACOSX_KQUEUE_IS_BROKEN 0
#endif /* defined(__ENVIRONMENT_MAC_OS_X_VERSION_MIN_REQUIRED__) */
#endif /* defined(__APPLE__) */

/** Initialize the threadlocals. Must be run before libevent is initialized. */
void
tor_evloop_init_threadlocals(void)
{
  tor_assert(tor_threadlocal_init(&eventloop_index) == 0);
}

/** Destroy the threadlocals. Must be run after tor_libevent_free_all. */
void
tor_evloop_destroy_threadlocals(void)
{
  tor_threadlocal_destroy(&eventloop_index);
}

/** Initialize the current thread. */
static void
init_eventloop_thread(int index)
{
  tor_assert(index >= 0 && index < num_eventloops);
  tor_assert(tor_threadlocal_get(&eventloop_index) == NULL);

  int* this_thread_index = tor_malloc(sizeof(int));
  *this_thread_index = index;
  tor_threadlocal_set(&eventloop_index, (void *)this_thread_index);
}

/* Destory the current thread. */
static void
destroy_eventloop_thread(void)
{
  int *this_thread_index = (int *)tor_threadlocal_get(&eventloop_index);
  if (this_thread_index != NULL) {
    tor_threadlocal_set(&eventloop_index, NULL);
    tor_free(this_thread_index);
  }
}

struct thread_data {
  void (*func)(void);
  int index;
};

static void
thread_wrapper(void *data_void)
{
  tor_assert(data_void != NULL);
  struct thread_data *data = (struct thread_data *)data_void;
  void (*func)(void) = data->func;
  int index = data->index;
  tor_free(data_void);

  init_eventloop_thread(index);
  func();
  destroy_eventloop_thread();
}

/* Start the eventloop threads and make them run 'func'. Threads will
   be started using 'spawn_fn'. */
void
start_eventloop_threads(void (*func)(void),
                        tor_thread_t *(*spawn_fn)(void (*func)(void *),
                                                  void *data))
{
  // the first thread (i==0) should already have been initialized
  for (int i=1; i<num_eventloops; i++) {
    struct thread_data *data = tor_malloc(sizeof(struct thread_data));
    data->func = func;
    data->index = i;
    tor_thread_t *thread = spawn_fn(thread_wrapper, (void *)data);
    tor_assert(thread != NULL);
    threads[i] = thread;
  }
}

/* Wait for the eventloop threads to finish. */
void
join_eventloop_threads(void)
{
  for (int i=1; i<num_eventloops; i++) {
    if (threads[i] != NULL) {
      tor_assert(join_thread(threads[i]) == 0);
      free_thread(threads[i]);
      threads[i] = NULL;
    }
  }
}

/** Initialize the Libevent library and set up the event base. */
void
tor_libevent_initialize(tor_libevent_cfg *torcfg,
                        int num_additional_eventloops)
{
  /* some paths below don't use torcfg, so avoid unused variable warnings */
  (void)torcfg;

  tor_assert(num_eventloops == -1);
  num_eventloops = num_additional_eventloops+1;
  eventloops = tor_malloc_zero(num_eventloops*sizeof(struct event_base *));
  threads = tor_malloc_zero(num_eventloops*sizeof(tor_thread_t *));
  rescan_eventloop_events = tor_malloc_zero(num_eventloops*sizeof(tor_thread_t *));

  /* This main thread has no tor_thread_t, so we set it to NULL. Should already
     be NULL from tor_malloc_zero, but we do this explicitly anyways. */
  threads[0] = NULL;

  int libevent_started_correctly = 1;

  {
    int attempts = 0;
    struct event_config *cfg;

    tor_assert(evthread_use_pthreads() == 0);

    ++attempts;
    cfg = event_config_new();
    tor_assert(cfg);

    if (torcfg->num_cpus > 0)
      event_config_set_num_cpus_hint(cfg, torcfg->num_cpus);

    /* We can enable changelist support with epoll, since we don't give
     * Libevent any dup'd fds.  This lets us avoid some syscalls. */
    event_config_set_flag(cfg, EVENT_BASE_FLAG_EPOLL_USE_CHANGELIST);

    for (int i=0; i<num_eventloops; i++) {
      eventloops[i] = event_base_new_with_config(cfg);
      rescan_eventloop_events[i] = event_new(eventloops[i], -1, 0,
                                             rescan_mainloop_cb,
                                             eventloops[i]);
      libevent_started_correctly = (libevent_started_correctly &&
                                    eventloops[i] != NULL &&
                                    rescan_eventloop_events[i] != NULL);
    }

    event_config_free(cfg);
  }

  if (libevent_started_correctly == 0) {
    /* LCOV_EXCL_START */
    log_err(LD_GENERAL, "Unable to initialize Libevent: cannot continue.");
    exit(1); // exit ok: libevent is broken.
    /* LCOV_EXCL_STOP */
  }

  /* Initialize this main thread. */
  init_eventloop_thread(0);

  log_info(LD_GENERAL,
      "Initialized libevent version %s using method %s. Good.",
      event_get_version(), tor_libevent_get_method());
}

/**
 * Return true iff the libevent module has been successfully initialized,
 * and not subsequently shut down.
 **/
bool
tor_libevent_is_initialized(void)
{
  return num_eventloops != -1;
}

/** Return the current Libevent event base that we're set up to use. */
MOCK_IMPL(struct event_base *,
tor_libevent_get_base, (void))
{
  int *index = tor_threadlocal_get(&eventloop_index);
  tor_assert(index != NULL);
  struct event_base *event_base = eventloops[*index];
  tor_assert(event_base != NULL);
  return event_base;
}

/** Return the name of the Libevent backend we're using. */
const char *
tor_libevent_get_method(void)
{
  struct event_base *event_base = tor_libevent_get_base();
  return event_base_get_method(event_base);
}

/** Return a string representation of the version of the currently running
 * version of Libevent. */
const char *
tor_libevent_get_version_str(void)
{
  return event_get_version();
}

/** Return a string representation of the version of Libevent that was used
* at compilation time. */
const char *
tor_libevent_get_header_version_str(void)
{
  return LIBEVENT_VERSION;
}

/** Represents a timer that's run every N microseconds by Libevent. */
struct periodic_timer_t {
  /** Underlying event used to implement this periodic event. */
  struct event *ev;
  /** The callback we'll be invoking whenever the event triggers */
  void (*cb)(struct periodic_timer_t *, void *);
  /** User-supplied data for the callback */
  void *data;
};

/** Libevent callback to implement a periodic event. */
static void
periodic_timer_cb(evutil_socket_t fd, short what, void *arg)
{
  periodic_timer_t *timer = arg;
  (void) what;
  (void) fd;
  timer->cb(timer, timer->data);
}

/** Create and schedule a new timer that will run every <b>tv</b> in
 * the event loop of <b>base</b>.  When the timer fires, it will
 * run the timer in <b>cb</b> with the user-supplied data in <b>data</b>. */
periodic_timer_t *
periodic_timer_new(struct event_base *base,
                   const struct timeval *tv,
                   void (*cb)(periodic_timer_t *timer, void *data),
                   void *data)
{
  periodic_timer_t *timer;
  tor_assert(base);
  tor_assert(tv);
  tor_assert(cb);
  timer = tor_malloc_zero(sizeof(periodic_timer_t));
  if (!(timer->ev = tor_event_new(base, -1, EV_PERSIST,
                                  periodic_timer_cb, timer))) {
    tor_free(timer);
    return NULL;
  }
  timer->cb = cb;
  timer->data = data;
  periodic_timer_launch(timer, tv);
  return timer;
}

/**
 * Launch the timer <b>timer</b> to run at <b>tv</b> from now, and every
 * <b>tv</b> thereafter.
 *
 * If the timer is already enabled, this function does nothing.
 */
void
periodic_timer_launch(periodic_timer_t *timer, const struct timeval *tv)
{
  tor_assert(timer);
  if (event_pending(timer->ev, EV_TIMEOUT, NULL))
    return;
  event_add(timer->ev, tv);
}

/**
 * Disable the provided <b>timer</b>, but do not free it.
 *
 * You can reenable the same timer later with periodic_timer_launch.
 *
 * If the timer is already disabled, this function does nothing.
 */
void
periodic_timer_disable(periodic_timer_t *timer)
{
  tor_assert(timer);
  (void) event_del(timer->ev);
}

/** Stop and free a periodic timer */
void
periodic_timer_free_(periodic_timer_t *timer)
{
  if (!timer)
    return;
  tor_event_free(timer->ev);
  tor_free(timer);
}

/**
 * Type used to represent events that run directly from the main loop,
 * either because they are activated from elsewhere in the code, or
 * because they have a simple timeout.
 *
 * We use this type to avoid exposing Libevent's API throughout the rest
 * of the codebase.
 *
 * This type can't be used for all events: it doesn't handle events that
 * are triggered by signals or by sockets.
 */
struct mainloop_event_t {
  struct event *ev;
  void (*cb)(mainloop_event_t *, void *);
  void *userdata;
};

/**
 * Internal: Implements mainloop event using a libevent event.
 */
static void
mainloop_event_cb(evutil_socket_t fd, short what, void *arg)
{
  (void)fd;
  (void)what;
  mainloop_event_t *mev = arg;
  mev->cb(mev, mev->userdata);
}

/**
 * As mainloop_event_cb, but implements a post-loop event.
 */
static void
mainloop_event_postloop_cb(evutil_socket_t fd, short what, void *arg)
{
  (void)fd;
  (void)what;

  /* Note that if rescan_mainloop_ev is already activated,
   * event_active() will do nothing: only the first post-loop event that
   * happens each time through the event loop will cause it to be
   * activated.
   *
   * Because event_active() puts events on a FIFO queue, every event
   * that is made active _after_ rescan_mainloop_ev will get its
   * callback run after rescan_mainloop_cb is called -- that is, on the
   * next iteration of the loop.
   */

  int *index = tor_threadlocal_get(&eventloop_index);
  tor_assert(index != NULL);
  struct event *rescan_event = rescan_eventloop_events[*index];
  tor_assert(rescan_event != NULL);
  event_active(rescan_event, EV_READ, 1);

  mainloop_event_t *mev = arg;
  mev->cb(mev, mev->userdata);
}

/**
 * Helper for mainloop_event_new() and mainloop_event_postloop_new().
 */
static mainloop_event_t *
mainloop_event_new_impl(int postloop,
                        void (*cb)(mainloop_event_t *, void *),
                        void *userdata)
{
  tor_assert(cb);

  struct event_base *base = tor_libevent_get_base();
  mainloop_event_t *mev = tor_malloc_zero(sizeof(mainloop_event_t));
  mev->ev = tor_event_new(base, -1, 0,
                  postloop ? mainloop_event_postloop_cb : mainloop_event_cb,
                  mev);
  tor_assert(mev->ev);
  mev->cb = cb;
  mev->userdata = userdata;
  return mev;
}

/**
 * Create and return a new mainloop_event_t to run the function <b>cb</b>.
 *
 * When run, the callback function will be passed the mainloop_event_t
 * and <b>userdata</b> as its arguments.  The <b>userdata</b> pointer
 * must remain valid for as long as the mainloop_event_t event exists:
 * it is your responsibility to free it.
 *
 * The event is not scheduled by default: Use mainloop_event_activate()
 * or mainloop_event_schedule() to make it run.
 */
mainloop_event_t *
mainloop_event_new(void (*cb)(mainloop_event_t *, void *),
                   void *userdata)
{
  return mainloop_event_new_impl(0, cb, userdata);
}

/**
 * As mainloop_event_new(), but create a post-loop event.
 *
 * A post-loop event behaves like any ordinary event, but any events
 * that _it_ activates cannot run until Libevent has checked for other
 * events at least once.
 */
mainloop_event_t *
mainloop_event_postloop_new(void (*cb)(mainloop_event_t *, void *),
                            void *userdata)
{
  return mainloop_event_new_impl(1, cb, userdata);
}

/**
 * Schedule <b>event</b> to run in the main loop, immediately.  If it is
 * not scheduled, it will run anyway. If it is already scheduled to run
 * later, it will run now instead.  This function will have no effect if
 * the event is already scheduled to run.
 *
 * This function may only be called from the main thread.
 */
void
mainloop_event_activate(mainloop_event_t *event)
{
  tor_assert(event);
  event_active(event->ev, EV_READ, 1);
}

/** Schedule <b>event</b> to run in the main loop, after a delay of <b>tv</b>.
 *
 * If the event is scheduled for a different time, cancel it and run
 * after this delay instead.  If the event is currently pending to run
 * <em>now</b>, has no effect.
 *
 * Do not call this function with <b>tv</b> == NULL -- use
 * mainloop_event_activate() instead.
 *
 * This function may only be called from the main thread.
 */
int
mainloop_event_schedule(mainloop_event_t *event, const struct timeval *tv)
{
  tor_assert(event);
  if (BUG(tv == NULL)) {
    // LCOV_EXCL_START
    mainloop_event_activate(event);
    return 0;
    // LCOV_EXCL_STOP
  }
  return event_add(event->ev, tv);
}

/** Cancel <b>event</b> if it is currently active or pending. (Do nothing if
 * the event is not currently active or pending.) */
void
mainloop_event_cancel(mainloop_event_t *event)
{
  if (!event)
    return;
  (void) event_del(event->ev);
}

/** Cancel <b>event</b> and release all storage associated with it. */
void
mainloop_event_free_(mainloop_event_t *event)
{
  if (!event)
    return;
  tor_event_free(event->ev);
  memset(event, 0xb8, sizeof(*event));
  tor_free(event);
}

int
tor_init_libevent_rng(void)
{
  int rv = 0;
  char buf[256];
  if (evutil_secure_rng_init() < 0) {
    rv = -1;
  }
  crypto_rand(buf, 32);
#ifdef HAVE_EVUTIL_SECURE_RNG_ADD_BYTES
  evutil_secure_rng_add_bytes(buf, 32);
#endif
  evutil_secure_rng_get_bytes(buf, sizeof(buf));
  return rv;
}

/**
 * Un-initialize libevent in preparation for an exit
 */
void
tor_libevent_free_all(void)
{
  /* Make sure all eventloop threads have stopped. */
  join_eventloop_threads();

  /* Destroy this main thread. Other eventloop threads should already have
     called this locally. */
  destroy_eventloop_thread();

  /* Destroy the rescan events since we own them. */
  for (int i=0; i<num_eventloops; i++) {
    event_free(rescan_eventloop_events[i]);
    rescan_eventloop_events[i] = NULL;
  }

  /* Destory the event bases since we own them. */
  for (int i=0; i<num_eventloops; i++) {
    event_base_free(eventloops[i]);
    eventloops[i] = NULL;
  }

  tor_free(eventloops);
  tor_free(threads);
  tor_free(rescan_eventloop_events);
  num_eventloops = -1;
}

/**
 * Run the event loop for the provided event_base, handling events until
 * something stops it.  If <b>once</b> is set, then just poll-and-run
 * once, then exit.  Return 0 on success, -1 if an error occurred, or 1
 * if we exited because no events were pending or active.
 *
 * This isn't reentrant or multithreaded.
 */
int
tor_libevent_run_event_loop(struct event_base *base, int once)
{
  const int flags = once ? EVLOOP_ONCE : 0;
  return event_base_loop(base, flags);
}

/** Tell the event loop to exit after <b>delay</b>.  If <b>delay</b> is NULL,
 * instead exit after we're done running the currently active events. */
void
tor_libevent_exit_loop_after_delay(struct event_base *base,
                                   const struct timeval *delay)
{
  event_base_loopexit(base, delay);
}

/** Tell the event loop to exit after running whichever callback is currently
 * active. */
void
tor_libevent_exit_loop_after_callback(struct event_base *base)
{
  event_base_loopbreak(base);
}

#if defined(TOR_UNIT_TESTS)
/** For testing: called post-fork to make libevent reinitialize
 * kernel structures. */
void
tor_libevent_postfork(void)
{
  int r = event_reinit(tor_libevent_get_base());
  tor_assert(r == 0);
}
#endif /* defined(TOR_UNIT_TESTS) */
