#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef nx_struct FakeMessage {
  NXSequenceNumber sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_hop_distance_t ultimate_sender_first_source_distance;

  nx_uint8_t message_type;

  nx_uint8_t ultimate_sender_fake_count;
  nx_uint32_t ultimate_sender_fake_duration_ms;
  nx_uint32_t ultimate_sender_fake_period_ms;

} FakeMessage;

inline SequenceNumberWithBottom Fake_get_sequence_number(const FakeMessage* msg) { return msg->sequence_number; }
inline am_addr_t Fake_get_source_id(const FakeMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_FAKEMESSAGE_H
