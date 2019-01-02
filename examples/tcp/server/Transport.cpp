#define _BUR_USE_DECLARATION_IN_IEC
#ifdef _DEFAULT_INCLUDES
#include "AsDefault.h"
#endif
#include "Transport.h"
/** \file Transport.cpp
 *  \brief Implementierung der Transport Klasse
 */

/**< Macros zum Setzen der Cursoren damit Buffer geschrieben werden*/
#define DECLARE_BUF() unsigned char m_buf[MAX_PAYLOAD], m_cursor = 0

#define PACK8(v) (m_buf[m_cursor] = (v), m_cursor++)
#define PACK16(v) (encode_16(*((unsigned long*)&(v)), m_buf + m_cursor), m_cursor += 2)
#define PACK32(v) (encode_32(*((unsigned long*)&(v)), m_buf + m_cursor), m_cursor += 4)
#define PACK64(v) (encode((v), m_buf + m_cursor), m_cursor +=8)

#define DECLARE_UNPACK() unsigned char m_cursor = 0
#define UNPACK8(v) (v) = payload[m_cursor]; m_cursor++
#define UNPACK32(v) (decode((v), payload + m_cursor), m_cursor += 4)
#define UNPACK64(v) (decode((v), payload + m_cursor), m_cursor += 8)
#define SEND_FRAME(v) (tcp->handleFrame((v), m_buf))


union {
	double var_double;
	struct {
		float var_float2;
		float var_float;
	};
	struct {
		unsigned long var_ulong2;
		unsigned long var_ulong;
	};
	struct {
		int var_int2;
		int :16; int :16; int var_int;
	};
	unsigned char var_byte[8];

} packunion;

void encode(double data, unsigned char buf[])
{
	packunion.var_double = data;
	for (int i = 0; i < 8; ++i)
		buf[i] = packunion.var_byte[7-i];
}


void encode_32(unsigned long data, unsigned char buf[])
{
	buf[0] = (unsigned short)((data & 0xff000000UL) >> 24);
	buf[1] = (unsigned short)((data & 0x00ff0000UL) >> 16);
	buf[2] = (unsigned short)((data & 0x0000ff00UL) >> 8);
	buf[3] = (unsigned short)(data & 0x000000ffUL);
}

static void encode_16(unsigned long data, unsigned char buf[])
{
	buf[0] = (unsigned short)((data & 0x0000ff00UL) >> 8);
	buf[1] = (unsigned short)(data & 0x000000ffUL);
}

void decode(float &var, unsigned char buf[])
{
	for (int i = 0; i < 4; ++i)
		packunion.var_byte[7-i] = buf[i];
	var = packunion.var_float;
}

void decode(double &var, unsigned char buf[])
{
	for (int i = 0; i < 8; ++i)
		packunion.var_byte[7-i] = buf[i];
	var = packunion.var_double;
}

void decode(unsigned long &var, unsigned char buf[])
{
	for (int i = 0; i < 4; ++i)
		packunion.var_byte[7-i] = buf[i];
	var = packunion.var_ulong;
}

void Transport::sendData()
{
#define FRAME_DESIRED_STUFF		(20)
#define FRAME_TEMP_HEATER_MEAS	(21)
#define FRAME_TEMP_COOLER_MEAS	(22)
#define FRAME_TEMP_HEATER_EST	(23)
#define FRAME_TEMP_COOLER_EST	(24)
#define FRAME_ACTUAL_STUFF		(25)

#define FRAME_DELAYS_HEATER		(26)
#define FRAME_DELAYS_COOLER		(27)
#define FRAME_OBSERVER_HEATER	(28)

#define FRAME_MANUAL_SET		(30)
#define FRAME_FF_CTRL_HEATER	(40)
#define FRAME_FB_CTRL_HEATER	(41)
#define FRAME_FF_CTRL_COOLER	(50)
#define FRAME_FB_CTRL_COOLER	(51)
#define FRAME_POWER_RAMP		(60)

#define FRAME_CONTROLLER_HEATER (42)
#define FRAME_CONTROLLER_COOLER	(52)

	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(T_So_in[0].celsius);
		PACK64(T_So_out[0].celsius);
		PACK64(T_Si_in[0].celsius);
		PACK64(T_Si_out[0].celsius);
		PACK64(T_amb1.celsius);
		SEND_FRAME(FRAME_TEMP_HEATER_MEAS);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(T_Si_in[1].celsius);
		PACK64(T_Si_out[1].celsius);
		PACK64(T_So_in[1].celsius);
		PACK64(T_So_out[1].celsius);
		PACK64(T_amb2.celsius);
		SEND_FRAME(FRAME_TEMP_COOLER_MEAS);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(T_TV_inh);
		PACK64(T_TV_outh);
		PACK64(T_SiV_outh);
		SEND_FRAME(FRAME_TEMP_HEATER_EST);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(T_SoT2_outh);
		PACK64(T_SiV2_outh);
		PACK64(T_TV2_outh);
		SEND_FRAME(FRAME_TEMP_COOLER_EST);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK32(Flow[0].actual.litre);
		PACK32(Flow[1].actual.litre);
		PACK32(Heater.percent);
		PACK64(CrossValve[0].actual.perc);
		PACK64(CrossValve[1].actual.perc);
		SEND_FRAME(FRAME_ACTUAL_STUFF);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(Tdes_VSo_in[0].celsius);
		PACK64(H_ff);
		PACK64(Tdes_So_in[0].celsius);
		PACK64(Tdes_So_out[0].celsius);
		PACK64(Tdes_VSo_in[0].celsius);
		PACK8(ff_u.transient);
		PACK8(ff_u.usertraj);
		SEND_FRAME(FRAME_CONTROLLER_HEATER);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(T_V2_out_ref);
		PACK64(T_Hx2_in_ref);
		PACK8(FF_cooler.transient);
		PACK8(FF_cooler.use_traj);
		SEND_FRAME(FRAME_CONTROLLER_COOLER);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(calc_tau_mdot[0].delay.So.sec);
		PACK64(calc_tau_mdot[0].delay.Si.sec);
		PACK64(calc_tau_mdot[0].delay.TV.sec);
		PACK64(calc_tau_mdot[0].delay.SoT.sec);
		PACK64(calc_tau_mdot[0].delay.TSi.sec);
		PACK64(calc_tau_mdot[0].delay.SiV.sec);
		PACK64(calc_tau_mdot[0].delay.VSo.sec);
		SEND_FRAME(FRAME_DELAYS_HEATER);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(calc_tau_mdot[1].delay.So.sec);
		PACK64(calc_tau_mdot[1].delay.Si.sec);
		PACK64(calc_tau_mdot[1].delay.TV.sec);
		PACK64(calc_tau_mdot[1].delay.SoT.sec);
		PACK64(calc_tau_mdot[1].delay.TSi.sec);
		PACK64(calc_tau_mdot[1].delay.SiV.sec);
		PACK64(calc_tau_mdot[1].delay.VSo.sec);
		SEND_FRAME(FRAME_DELAYS_COOLER);
	}
	{
		DECLARE_BUF();
		PACK32(this->lTime);
		PACK64(Th_SiV_out.celsius);
		PACK64(Th_SoT_in.celsius);
		PACK64(Th_SoT_out.celsius);
		PACK64(Th_TV_out.celsius);
		PACK64(Th_VSo_out.celsius);
		SEND_FRAME(FRAME_OBSERVER_HEATER);
	}
}

void unpackDS(unsigned char *payload)
{
	DECLARE_UNPACK();
	UNPACK32(Flow[0].desired.litre);
	UNPACK32(Flow[1].desired.litre);
	UNPACK32(SpeedCon_perc);
}

void unpackPR(unsigned char *payload)
{
	DECLARE_UNPACK();
	UNPACK32(pr_P_start);
	UNPACK32(pr_P_end);
	UNPACK32(pr_Time);
	UNPACK8(pr_enable);
}

void unpackFF(unsigned char *payload, bool cooler)
{
	DECLARE_UNPACK();
	UNPACK8(use_FF[cooler]);
	UNPACK64(ff_inputs[cooler].Tdes);
	UNPACK64(ff_inputs[cooler].deltaT);
	UNPACK64(ff_inputs[cooler].scale_t);
}

void unpackFB(unsigned char *payload, bool cooler)
{
	DECLARE_UNPACK();
	UNPACK8(use_FB[cooler]);
	UNPACK64(fub_pid[cooler].LowLim);
	UNPACK64(fub_pid[cooler].UpLim);
	UNPACK64(fub_pid[cooler].P);
	UNPACK64(fub_pid[cooler].D);
	UNPACK64(fub_pid[cooler].N);
	UNPACK64(fub_pid[cooler].I);
}

void unpackM(unsigned char *payload)
{
	DECLARE_UNPACK();
	UNPACK32(Heater.percent);
	UNPACK64(CrossValve[0].desired.perc);
	UNPACK64(CrossValve[1].desired.perc);
}

void unpackInData(unsigned char *payload)
{
	DECLARE_UNPACK();
	UNPACK32(TestFloat);
	UNPACK32(TestLong);
	UNPACK64(TestDouble);
}

void Transport::handleFrame(unsigned char id, unsigned char *payload)
{
	switch(id)
	{
		case 1:
			unpackExp(payload);
			break;
		case FRAME_DESIRED_STUFF:
			unpackDS(payload);
			break;
		case FRAME_POWER_RAMP:
			unpackPR(payload);
			break;
		case FRAME_FF_CTRL_HEATER:
			unpackFF(payload, 0);
			break;
		case FRAME_FF_CTRL_COOLER:
			unpackFF(payload, 1);
			break;
		case FRAME_FB_CTRL_HEATER:
			unpackFB(payload, 0);
			break;
		case FRAME_FB_CTRL_COOLER:
			unpackFB(payload, 1);
			break;
		case FRAME_MANUAL_SET:
			unpackM(payload);
			break;
		case 99:
			unpackInData(payload);
			break;
		default:
			;
	}
}



void Transport::unpackExp(unsigned char *payload)
{
	/* Setze oder Lösche Experimenten Aktivationsflag*/
	DECLARE_UNPACK();
	UNPACK8(this->bActivateExperiment);
	this->lTime = 0;
}

void Transport::registerServer(Comm *serv)
{
	this->tcp = serv;
}