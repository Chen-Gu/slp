#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	CHOOSE_CHANNEL = 3,
	FAKE_CHANNEL = 4,
	BEACON_CHANNEL = 5,
    NOTIFY_CHANNEL = 6,
};

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 6
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 10

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (5 * 1000)

#endif // SLP_CONSTANTS_H
