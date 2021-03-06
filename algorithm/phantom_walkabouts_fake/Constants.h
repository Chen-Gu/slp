#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	BEACON_CHANNEL = 3,
	FAKE_CHANNEL = 4
};

typedef struct
{
	int16_t address;
	int16_t neighbour_size;
}neighbour_info;

typedef struct
{
	int16_t address;
	int16_t neighbour_size;
}chosen_set_neighbour;
	
typedef struct
{
	int16_t message_sent;
	int16_t sequence_message_sent;
	int16_t probability;
}RandomWalk;

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20

#define SLP_MAX_NUM_AWAY_MESSAGES 4
#define MAX_NUM_NEIGHBOURS 2 //max neighbours each direction

#define BOTTOMLEFT 0
#define BOTTOMRIGHT 1
#define SINK 2
#define TOPRIGHT 3

#define LONG_RANDOM_WALK_RECEIVE_RATIO 0.3

#define SLP_MAX_1_HOP_NEIGHBOURHOOD 4
#define SLP_MAX_SET_NEIGHBOURS 2

#define NODE_TRANSMIT_TIME 6

#endif // SLP_CONSTANTS_H
