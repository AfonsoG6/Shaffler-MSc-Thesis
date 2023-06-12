#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "core/mainloop/throughput_logging.h"

#include "lib/lock/compat_mutex.h"
#include "lib/smartlist_core/smartlist_core.h"
#include "lib/thread/threads.h"
#include "lib/malloc/malloc.h"
#include "lib/log/util_bug.h"

const unsigned int timestep_ms = 500;

bool throughput_logging_enabled = false;
monotime_coarse_t throughput_logging_coarse_start_time;
// NOTE: we don't lock these variables, so make sure they are set
// before any threads have started, and that they don't change
// while threads are running

double throughput_logging_wall_start_time;
tor_mutex_t throughput_logging_lock;

smartlist_t **sent_lists = NULL;
smartlist_t **recv_lists = NULL;
tor_mutex_t *bytes_list_mutexes = NULL;
int relay_bytes_lists_len = -1;

tor_threadlocal_t thread_sent_list;
tor_threadlocal_t thread_recv_list;
tor_threadlocal_t thread_logging_mutex;

// only call if no threads are running
void
init_throughput_logging(int num_threads)
{
  tor_assert(!throughput_logging_enabled);

  tor_mutex_init(&throughput_logging_lock);
  tor_mutex_acquire(&throughput_logging_lock);

  relay_bytes_lists_len = num_threads;

  monotime_coarse_get(&throughput_logging_coarse_start_time);
  struct timeval ts;
  gettimeofday(&ts, NULL);
  throughput_logging_wall_start_time = ts.tv_sec+(ts.tv_usec/1000000.0);

  sent_lists = tor_malloc_zero(num_threads*sizeof(smartlist_t *));
  recv_lists = tor_malloc_zero(num_threads*sizeof(smartlist_t *));
  bytes_list_mutexes = tor_malloc_zero(num_threads*sizeof(tor_mutex_t));
  for (int i=0; i<num_threads; i++) {
    tor_mutex_init(&bytes_list_mutexes[i]);
    tor_mutex_acquire(&bytes_list_mutexes[i]);
    sent_lists[i] = smartlist_new();
    recv_lists[i] = smartlist_new();
    tor_mutex_release(&bytes_list_mutexes[i]);
  }

  tor_threadlocal_init(&thread_sent_list);
  tor_threadlocal_init(&thread_recv_list);
  tor_threadlocal_init(&thread_logging_mutex);

  throughput_logging_enabled = true;
  tor_mutex_release(&throughput_logging_lock);
}

// only call if no threads are running
void
destroy_throughput_logging(void)
{
  tor_assert(throughput_logging_enabled);

  tor_mutex_acquire(&throughput_logging_lock);

  for (int i=0; i<relay_bytes_lists_len; i++) {
    tor_mutex_acquire(&bytes_list_mutexes[i]);

    smartlist_free(sent_lists[i]);
    smartlist_free(recv_lists[i]);
    sent_lists[i] = NULL;
    recv_lists[i] = NULL;

    tor_mutex_release(&bytes_list_mutexes[i]);
    tor_mutex_uninit(&bytes_list_mutexes[i]);
  }

  tor_free(bytes_list_mutexes);
  tor_free(sent_lists);
  tor_free(recv_lists);
  relay_bytes_lists_len = -1;

  tor_threadlocal_destroy(&thread_sent_list);
  tor_threadlocal_destroy(&thread_recv_list);
  tor_threadlocal_destroy(&thread_logging_mutex);

  throughput_logging_enabled = false;

  tor_mutex_release(&throughput_logging_lock);
  tor_mutex_uninit(&throughput_logging_lock);
}

void
init_thread_throughput_logging(int thread_id)
{
  tor_assert(throughput_logging_enabled);

  tor_mutex_acquire(&throughput_logging_lock);

  tor_assert(thread_id < relay_bytes_lists_len && thread_id >= 0);
  tor_threadlocal_set(&thread_logging_mutex, &bytes_list_mutexes[thread_id]);
  tor_mutex_acquire(&bytes_list_mutexes[thread_id]);
  // we acquire this mutex for the lifetime of the thread, hope nobody
  // tries to acquire it :)

  tor_threadlocal_set(&thread_sent_list, sent_lists[thread_id]);
  tor_threadlocal_set(&thread_recv_list, recv_lists[thread_id]);

  tor_mutex_release(&throughput_logging_lock);
}

void
destroy_thread_throughput_logging(void)
{
  tor_assert(throughput_logging_enabled);

  tor_threadlocal_set(&thread_sent_list, NULL);
  tor_threadlocal_set(&thread_recv_list, NULL);

  tor_mutex_t *mutex = tor_threadlocal_get(&thread_logging_mutex);
  if (mutex != NULL) {
    tor_mutex_release(mutex);
    tor_threadlocal_set(&thread_logging_mutex, NULL);
  }
}

static void
log_throughput(smartlist_t *list, uint32_t bytes, monotime_coarse_t *time)
{
  tor_assert(throughput_logging_enabled);

  int64_t ms_since_start = monotime_coarse_diff_msec(&throughput_logging_coarse_start_time, time);
  int list_index = ms_since_start/timestep_ms;

  if (list_index >= smartlist_len(list)) {
    // need to grow the list
    int additional_elements = (60000-1)/timestep_ms + 1;
    // want an extra 60 seconds, and we want the ceil
    int new_size = (list_index+1)+additional_elements;
    // want enough room to store the current value, plus an extra 60 seconds
    smartlist_grow(list, new_size);
  }

  uint32_t old_bytes = (intptr_t)smartlist_get(list, list_index);
  uint32_t new_bytes = old_bytes+bytes;
  if (new_bytes < old_bytes) {
    new_bytes = UINT32_MAX;
  }
  smartlist_set(list, list_index, (void *)(intptr_t)new_bytes);
}

void
log_sent_bytes(uint32_t bytes, monotime_coarse_t *now)
{
  if (bytes > 0 && throughput_logging_enabled) {
    smartlist_t *sent_list = tor_threadlocal_get(&thread_sent_list);
    tor_assert(sent_list != NULL);
    log_throughput(sent_list, bytes, now);
  }
}

void
log_recv_bytes(uint32_t bytes, monotime_coarse_t *now)
{
  if (bytes > 0 && throughput_logging_enabled) {
    smartlist_t *recv_list = tor_threadlocal_get(&thread_recv_list);
    tor_assert(recv_list != NULL);
    log_throughput(recv_list, bytes, now);
  }
}

// only run this function when the threads have finished
void
write_throughput_log(char *file_name)
{
  if (!throughput_logging_enabled) {
    log_warn(LD_CONFIG, "Throughput logging was not set up, so didn't write to log file");
    return;
  }

  tor_mutex_acquire(&throughput_logging_lock);

  if (file_name == NULL || strlen(file_name) == 0) {
    log_warn(LD_CONFIG, "Was not given a file name for the throughput log");
    tor_mutex_release(&throughput_logging_lock);
    return;
  }

  FILE *log_file = fopen(file_name, "w");

  if (log_file == NULL) {
    log_warn(LD_CONFIG, "Could not open throughput log file %s", file_name);
    tor_mutex_release(&throughput_logging_lock);
    return;
  }

  for (int i=0; i<relay_bytes_lists_len; i++) {
    tor_mutex_acquire(&bytes_list_mutexes[i]);
    // this will block if any threads have not finished
  }

  struct timeval ts;
  gettimeofday(&ts, NULL);
  double current_time = ts.tv_sec+(ts.tv_usec/1000000.0);

  // write header
  fprintf(log_file, "time          ");
  for (int i=0; i<relay_bytes_lists_len; i++) {
    for (int j=0; j<2; j++) {
      fprintf(log_file, ", thrd %d %s", 0, (j==0)?"sent":"recv");
    }
  }
  fprintf(log_file, "\n");

  // write data
  bool thread_had_data = true;
  int time_index = 0;
  while (thread_had_data) {
    // write line
    thread_had_data = false;
    double logging_time = throughput_logging_wall_start_time+(time_index*timestep_ms/1000.0);
    fprintf(log_file, "%.3f", logging_time);

    for (int i=0; i<relay_bytes_lists_len; i++) {
      // write column
      smartlist_t *sent_list = sent_lists[i];
      smartlist_t *recv_list = recv_lists[i];
      uint32_t bytes_sent = 0;
      uint32_t bytes_recv = 0;

      if (time_index < smartlist_len(sent_list)) {
        bytes_sent = (intptr_t)smartlist_get(sent_list, time_index);
        if (logging_time <= current_time || bytes_sent != 0) {
          thread_had_data = true;
        }
      }
      if (time_index < smartlist_len(recv_list)) {
        bytes_recv = (intptr_t)smartlist_get(recv_list, time_index);
        if (logging_time <= current_time || bytes_recv != 0) {
          thread_had_data = true;
        }
      }

      fprintf(log_file, ", %11"PRIu32", %11"PRIu32, bytes_sent, bytes_recv);
    }

    time_index += 1;
    fprintf(log_file, "\n");
  }

  for (int i=0; i<relay_bytes_lists_len; i++) {
    tor_mutex_release(&bytes_list_mutexes[i]);
  }

  fclose(log_file);

  tor_mutex_release(&throughput_logging_lock);
}
