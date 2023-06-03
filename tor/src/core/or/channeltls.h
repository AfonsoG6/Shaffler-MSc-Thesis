/* * Copyright (c) 2012-2021, The Tor Project, Inc. */
/* See LICENSE for licensing information */

/**
 * \file channeltls.h
 * \brief Header file for channeltls.c
 **/

#ifndef TOR_CHANNELTLS_H
#define TOR_CHANNELTLS_H

#include "core/or/or.h"
#include "core/or/channel.h"

struct ed25519_public_key_t;
struct curve25519_public_key_t;

#define TLS_PER_CELL_OVERHEAD 29

#define BASE_CHAN_TO_TLS(c) (channel_tls_from_base((c)))
#define TLS_CHAN_TO_BASE(c) (channel_tls_to_base((c)))
#define CONST_BASE_CHAN_TO_TLS(c) (channel_tls_from_base_const((c)))
#define CONST_TLS_CHAN_TO_BASE(c) (channel_tls_to_base_const((c)))

#define TLS_CHAN_MAGIC 0x8a192427U

#ifdef CHANNEL_OBJECT_PRIVATE

struct channel_tls_t {
  /* Base channel_t struct */
  channel_t base_;
  /* or_connection_t pointer */
  or_connection_t *conn;
};

#endif /* defined(CHANNEL_OBJECT_PRIVATE) */

channel_t * channel_tls_connect(const tor_addr_t *addr, uint16_t port,
                                const char *id_digest,
                                const struct ed25519_public_key_t *ed_id);
channel_listener_t * channel_tls_get_listener(void);
channel_listener_t * channel_tls_start_listener(void);
channel_t * channel_tls_handle_incoming(or_connection_t *orconn);

/* Casts */

channel_t * channel_tls_to_base(channel_tls_t *tlschan);
channel_tls_t * channel_tls_from_base(channel_t *chan);
const channel_t * channel_tls_to_base_const(const channel_tls_t *tlschan);
const channel_tls_t * channel_tls_from_base_const(const channel_t *chan);

/* Things for connection_or.c to call back into */
void channel_tls_handle_cell(cell_t *cell, or_connection_t *conn);
void channel_tls_handle_state_change_on_orconn(channel_tls_t *chan,
                                               or_connection_t *conn,
                                               uint8_t state);
void channel_tls_handle_var_cell(var_cell_t *var_cell,
                                 or_connection_t *conn);
void channel_tls_update_marks(or_connection_t *conn);

/* Cleanup at shutdown */
void channel_tls_free_all(void);

extern uint64_t stats_n_authorize_cells_processed;
extern uint64_t stats_n_authenticate_cells_processed;
extern uint64_t stats_n_versions_cells_processed;
extern uint64_t stats_n_netinfo_cells_processed;
extern uint64_t stats_n_vpadding_cells_processed;
extern uint64_t stats_n_certs_cells_processed;
extern uint64_t stats_n_auth_challenge_cells_processed;

#ifdef CHANNELTLS_PRIVATE
STATIC void channel_tls_process_certs_cell(var_cell_t *cell,
                                           channel_tls_t *tlschan);
STATIC void channel_tls_process_auth_challenge_cell(var_cell_t *cell,
                                                    channel_tls_t *tlschan);
STATIC void channel_tls_common_init(channel_tls_t *tlschan);
STATIC void channel_tls_process_authenticate_cell(var_cell_t *cell,
                                                  channel_tls_t *tlschan);
#  endif /* defined(CHANNELTLS_PRIVATE) */

int probably_middle_node(or_connection_t *conn, circuit_t *circ);

struct timespec get_sleep_timespec_from_command(uint8_t command);

unsigned bitcount32(uint32_t x);

unsigned clz32(uint32_t x);

double gen_random_uniform_01(void);

double gen_normal_variate(void);

double gen_normal_value(double location, double scale);

double gen_lognormal_value(double location, double scale);

void update_circ_delay_state(circuit_t *circ);

double generate_delay(short delay_state);

double get_delay_microseconds(circuit_t *circ);

double get_delay_scale_factor(uint8_t command);

struct timespec get_delay_timespec(circuit_t *circ, uint8_t command);

#endif /* !defined(TOR_CHANNELTLS_H) */
