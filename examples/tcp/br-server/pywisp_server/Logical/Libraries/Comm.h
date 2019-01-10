#ifndef COMM_H
#define COMM_H

#define MAX_PAYLOAD (80)

class Comm {
	public:
	struct frame {
		unsigned char id;
		unsigned char payload[MAX_PAYLOAD];
	};
	virtual void handleFrame(unsigned char id, unsigned char buf[MAX_PAYLOAD]) = 0;
};

#endif
