#include <bur/plc.h>
#include <bur/plctypes.h>
#include <limits>

#ifdef _DEFAULT_INCLUDES
	#include <AsDefault.h>
#endif

#include "../Libraries/Transport/Transport.h"

// amount of memory to be allocated for heap storage must be specified for every ANSI C++ program with the bur_heap_size variable
unsigned long bur_heap_size = 0xFFFF;

/**
 * @brief Method that calculates the ramp trajectory value at benchData.lTime and writes it to trajData.dOutput
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

/**
 * @brief Method that interpolates the series received from pyWisp linearly at benchData.lTime and writes the value
 * to trajData.dSeriesOutput, 0 without a series
 */
void fSeries() {
	const unsigned short n = trajData.uiSeriesPoints;
	const double *t = trajData.adSeries;
	const double *v = trajData.adSeries + n;
	const double x = benchData.lTime;
	if (n == 0) {
		trajData.dSeriesOutput = 0;
	} else if (x <= t[0]) {
		trajData.dSeriesOutput = v[0];
	} else {
		trajData.dSeriesOutput = v[n - 1];
		for (unsigned short i = 1; i < n; ++i) {
			if (x < t[i]) {
				/* t[i - 1] < x < t[i], no division by zero */
				trajData.dSeriesOutput = v[i - 1] + (v[i] - v[i - 1]) * (x - t[i - 1]) / (t[i] - t[i - 1]);
				break;
			}
		}
	}
}

void _INIT ProgramInit(void) {
	benchData.lTime = 0;
	benchData.dValue1 = 0;
	benchData.fValue2 = 0;
	benchData.iValue3 = 0;
	benchData.cValue4 = 0;
	benchData.dValueNan = std::numeric_limits<double>::quiet_NaN();
	benchData.dValueInf = std::numeric_limits<double>::infinity();

	trajData.dStartValue = 0;
	trajData.lStartTime = 0;
	trajData.dEndValue = 0;
	trajData.lEndTime = 0;
	trajData.dOutput = 0;
	trajData.uiSeriesPoints = 0;
	trajData.dSeriesOutput = 0;
}

/** runs in Cyclic#4 (100 ms) before TcpIpServer, so both see the same data */
void _CYCLIC ProgramCyclic(void)
{
	fTrajectory();
	fSeries();
}

void _EXIT ProgramExit(void)
{
}
