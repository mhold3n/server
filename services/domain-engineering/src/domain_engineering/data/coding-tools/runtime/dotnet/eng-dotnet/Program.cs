using MathNet.Numerics;
using System.Reflection;
using UnitsNet;

var length = Length.FromMeters(1.0);
var gamma = SpecialFunctions.Gamma(5);
var picoAssembly = Assembly.Load("PicoGK");
Console.WriteLine($"UnitsNet:{length.Meters};MathNet:{gamma};PicoGK:{picoAssembly.GetName().Version}");
