#include <bur/plc.h>
#include <bur/plctypes.h>
#include <math.h>

#ifdef _DEFAULT_INCLUDES
	#include <AsDefault.h>
#endif

#include "../Libraries/Transport/Transport.h"

// amount of memory to be allocated for heap storage must be specified for every ANSI C++ program with the bur_heap_size variable
unsigned long bur_heap_size = 0xFFFF;
const unsigned long lDt = 1000;          ///< Sampling step [ms]

/**
 * @brief Method that calculates a trajectory value and writes the return value in _trajData->dOutput
 * @param _benchData pointer to test rig data struct
 * @param _trajData pointer to trajectory struct
 */
void fTrajectory() {
	if (benchData.lTime < trajData.lStartTime) {
		trajData.dOutput = trajData.dStartValue;
	} else {
		if (benchData.lTime < trajData.lEndTime) {
			double dM = (trajData.dEndValue - trajData.dStartValue) / (trajData.lEndTime - trajData.lStartTime);
			double dN = trajData.dEndValue - dM * trajData.lEndTime;
			trajData.dOutput = dM * benchData.lTime + dN;
		} else {
			trajData.dOutput = trajData.dEndValue;
		}
	}
}

void _INIT ProgramInit(void) {
	benchData.lTime = 0;
	benchData.dValue1 = 0;
	benchData.fValue2 = 0;
	benchData.iValue3 = 0;
	benchData.cValue4 = 0;
	benchData.dValueNan = nan("");
	benchData.dValueInf =  infinity();
	
	trajData.dStartValue = 0;
	trajData.lStartTime = 0;
	trajData.dEndValue = 0;
	trajData.lEndTime = 0;
	trajData.dOutput = 0;
}

void _CYCLIC ProgramCyclic(void)
{
		fTrajectory();
}

void _EXIT ProgramExit(void)
{
	// Insert code here 

}
