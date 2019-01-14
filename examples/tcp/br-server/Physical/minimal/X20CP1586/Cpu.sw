<?xml version="1.0" encoding="utf-8"?>
<?AutomationStudio Version=4.4.6.71 SP?>
<SwConfiguration CpuAddress="SL1" xmlns="http://br-automation.co.at/AS/SwConfiguration">
  <TaskClass Name="Cyclic#1" />
  <TaskClass Name="Cyclic#2" />
  <TaskClass Name="Cyclic#3" />
  <TaskClass Name="Cyclic#4">
    <Task Name="TCP_Server" Source="TCP_Server.prg" Memory="UserROM" Language="ANSIC" Debugging="true" />
  </TaskClass>
  <TaskClass Name="Cyclic#5" />
  <TaskClass Name="Cyclic#6" />
  <TaskClass Name="Cyclic#7">
    <Task Name="ControlLoo" Source="ControlLoop.prg" Memory="UserROM" Language="ANSIC" Debugging="true" />
  </TaskClass>
  <TaskClass Name="Cyclic#8" />
  <Libraries>
    <LibraryObject Name="AsBrStr" Source="Libraries.AsBrStr.lby" Memory="UserROM" Language="Binary" Debugging="true" />
    <LibraryObject Name="AsIOTime" Source="Libraries.AsIOTime.lby" Memory="UserROM" Language="Binary" Debugging="true" />
    <LibraryObject Name="AsTCP" Source="Libraries.AsTCP.lby" Memory="UserROM" Language="Binary" Debugging="true" />
    <LibraryObject Name="runtime" Source="Libraries.runtime.lby" Memory="UserROM" Language="Binary" Debugging="true" />
    <LibraryObject Name="TCPServer" Source="Libraries.TCPServer.lby" Memory="None" Language="ANSIC" Debugging="true" />
    <LibraryObject Name="Transport" Source="Libraries.Transport.lby" Memory="None" Language="ANSIC" Debugging="true" />
    <LibraryObject Name="Frame" Source="Libraries.Frame.lby" Memory="None" Language="ANSIC" Debugging="true" />
  </Libraries>
</SwConfiguration>