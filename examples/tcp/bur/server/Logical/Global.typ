
TYPE
	_expData : 	STRUCT 
		bActivateExperiment : BOOL;
	END_STRUCT;
	_trajData : 	STRUCT 
		dStartValue : LREAL;
		lStartTime : UDINT;
		dEndValue : LREAL;
		lEndTime : UDINT;
		dOutput : LREAL;
	END_STRUCT;
	_benchData : 	STRUCT 
		lTime : UDINT;
		dValue1 : LREAL;
		fValue2 : REAL;
		iValue3 : INT;
		cValue4 : BYTE;
		dValueNan : LREAL;
		dValueInf : LREAL;
	END_STRUCT;
END_TYPE
