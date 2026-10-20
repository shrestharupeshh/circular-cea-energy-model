# Circular CEA Energy Model

A coupled energy and water balance simulation of a closed, lit, controlled-environment growing room, written in Python. It asks one question: **what does it cost, in electricity and in water, to make a vertical-farm growing room circular?**

> **Status: work in progress.** The model, tests and sensitivity study are working. The written assumptions, the validation document and some figures are still being finished, and all numbers below are preliminary.

## The question

A closed growing room turns almost all of its lighting electricity into heat, and its crop transpires several litres of water per kilogram of produce. A conventional ("linear") room cools the air, vents the humid air and throws both the heat and the water away. A circular room can capture both. Capturing them is not free, so the interesting question is the trade-off:

- **A, linear:** no recovery. Waste heat is rejected, transpired water is vented, and the room is heated from the grid when it is cold.
- **B, heat recovery:** heat removed by the cooling system is stored in a thermal buffer tank and later used to heat the room.
- **C, heat and water recovery:** as B, plus a dehumidifier that condenses transpired water for reuse in irrigation.

All three scenarios see the same weather, the same lights and the same crop.


Rupesh Shrestha, mechanical engineer (MEng, UC Berkeley). [shrestharupesh.com](https://www.shrestharupesh.com)

This project is designed with the help of Claude AI for the purpose of self training to learn system dynamic modeling in CEA.

Built as a self-directed project on dynamic systems modelling for controlled-environment agriculture. The model structure follows a self-study guide. An AI assistant was used for explanation and code review; the code was written and run by the author.
