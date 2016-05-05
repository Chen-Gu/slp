#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct FakeMessage {
  NXSequenceNumber sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_int32_t sender_min_source_distance;

} FakeMessage;

inline SequenceNumberWithBottom Fake_get_sequence_number(const FakeMessage* msg) { return msg->sequence_number; }
inline int32_t Fake_get_source_id(const FakeMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_FAKEMESSAGE_H
