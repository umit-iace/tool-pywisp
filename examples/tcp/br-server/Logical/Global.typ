
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
	END_STRUCT;
	TcpServer_interface : 	STRUCT 
		out_Encoder_Achse_1 : REAL;
		out_Encoder_Motor : REAL;
		out_Statusword : UINT;
		out_ActualValue : REAL;
		in_Controlword : UINT;
		in_Setpoint : REAL;
		tmp : ARRAY[0..3]OF USINT;
	END_STRUCT;
	TcpServer_instances : 	STRUCT 
		TcpOpen_0 : TcpOpen;
		TcpServer_0 : TcpServer;
		TcpIoctl_0 : TcpIoctl;
		TcpRecv_0 : TcpRecv;
		TcpSend_0 : TcpSend;
		TcpClose_0 : TcpClose;
		linger_opt : tcpLINGER_typ;
	END_STRUCT;
END_TYPE
