#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
};

#define SLP_MAX_NUM_SOURCES 1
#define SLP_MAX_NUM_SINKS 1

#define AWAY_DELAY_MS 200

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (5 * 1000)

#endif // SLP_CONSTANTS_H
