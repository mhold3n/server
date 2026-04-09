using MathNet.Numerics;
using UnitsNet;

var length = Length.FromMeters(1.0);
var gamma = SpecialFunctions.Gamma(5);
Console.WriteLine($"UnitsNet:{length.Meters};MathNet:{gamma}");
