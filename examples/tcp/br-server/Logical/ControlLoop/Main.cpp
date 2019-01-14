
#include <bur/plctypes.h>
#include "../Libraries/Transport/Transport.h"

#ifdef _DEFAULT_INCLUDES
	#include <AsDefault.h>
#endif

Transport transport;

// amount of memory to be allocated for heap storage must be specified for every ANSI C++ program with the bur_heap_size variable
unsigned long bur_heap_size = 0xFFFF; 
const unsigned long lDt = 1000;          ///< Sampling step [ms]

/**
 * @brief Method that calculates a trajectory value and writes the return value in _trajData->dOutput
 * @param _benchData pointer to test rig data struct
 * @param _trajData pointer to trajectory struct
 */
void fTrajectory(struct Transport::benchData *_benchData, struct Transport::trajData *_trajData) {
	if (_benchData->lTime < _trajData->lStartTime) {
		_trajData->dOutput = _trajData->dStartValue;
	} else {
		if (_benchData->lTime < _trajData->lEndTime) {
			double dM = (_trajData->dEndValue - _trajData->dStartValue) / (_trajData->lEndTime - _trajData->lStartTime);
			double dN = _trajData->dEndValue - dM * _trajData->lEndTime;
			_trajData->dOutput = dM * _benchData->lTime + dN;
		} else {
			_trajData->dOutput = _trajData->dEndValue;
		}
	}
}

void _INIT ProgramInit(void)
{
	// Insert code here 

}

void _CYCLIC ProgramCyclic(void)
{
	if (transport.runExp()) {
		transport._benchData.lTime += lDt;

		fTrajectory(&transport._benchData, &transport._trajData);

		transport.sendData();
	}
}

void _EXIT ProgramExit(void)
{
	// Insert code here 

}
