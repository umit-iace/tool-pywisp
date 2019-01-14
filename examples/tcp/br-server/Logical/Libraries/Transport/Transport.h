#ifndef TRANSPORT_CLASS_H
#define TRANSPORT_CLASS_H

#include "../Comm.h"
#include "../Frame/Frame.h"
/** \file Transport.h
 *  \class Transport
 *  \brief Klasse zum Ent- und Packen der Kommunikationsdaten zu Pywisp
 *
 *  Die Klasse wird mit zwei Buffer initialisiert, einen Eingangsbuffer und
 *  einen Ausgangsbuffer. Diese Buffer müssen die gleiche Länge besitzen wie
 *  die auf Pywisp. Will man mehrere Frames schicken, so können weitere Buffer
 *  über die addOutBuffer() Methode hinzugefügt werden. Damit diese auch
 *  gesendet werden, muss entsprechender Frame in sendData() gepackt werden.
 *  Eingangsseitig gibt es nur einen Buffer der die Frames liefert. Mit
 *  der Methode run() kann kontrolliert werden, ob Eingangsseitig Daten
 *  ausgewertet werden müssen. Mittels runExp() kann kontrolliert werden
 *  ob ein Experiment ausgeführt werden soll.
 */

class Transport: public Comm{
	public:
	/**< Rückgabe des Experimenten Flags*/
	bool runExp() { return this->bActivateExperiment; }

	void handleFrame(Frame frame);

	void sendData();
	
	void registerServer(Comm *serv);

	struct benchData {
		unsigned long lTime;                    ///< seconds since start of experiment
		double dValue1;
		float fValue2;
		int iValue3;
		unsigned char cValue4;
	} _benchData;

	struct trajData {
		double dStartValue;          ///< start value of the trajectory
		unsigned long lStartTime;      ///< start time of the trajectory
		double dEndValue;            ///< end value of the trajectory
		unsigned long lEndTime;        ///< end time of the trajectory
		double dOutput;             ///< output value of the trajectory
	} _trajData;

	private:
	Comm *tcp;
	bool bActivateExperiment;

	void unpackExp(Frame frame);

	void unpackBenchData(Frame frame);

	void unpackTrajRampData(Frame frame);

};

extern Transport transport;

#endif //TRANSPORT_CLASS_H
