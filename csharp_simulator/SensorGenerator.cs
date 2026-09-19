namespace DisplayFab.Proc01Simulator;

// Python Simulator의 SensorGenerator와 같은 역할.
// OLED Evap 학습용 범위다. 실제 증착 스펙이 아니다.

public class SensorGenerator
{
    private readonly Random _random = new();

    public (double Temperature, double Pressure) Next(string recipeId, string fault)
    {
        double tMin = 112.0;
        double tMax = 128.0;
        double pMin = 0.0032;
        double pMax = 0.0075;

        if (recipeId == "RCP-OLED-B01")
        {
            tMin = 142.0;
            tMax = 158.0;
            pMin = 0.0022;
            pMax = 0.0055;
        }

        if (recipeId == "RCP-LCD-C01")
        {
            tMin = 82.0;
            tMax = 93.0;
            pMin = 0.85;
            pMax = 1.15;
        }

        double temperature = tMin + _random.NextDouble() * (tMax - tMin);
        double pressure = pMin + _random.NextDouble() * (pMax - pMin);

        if (fault == "TEMPERATURE_OUT_OF_RANGE")
        {
            temperature = 210.0;
        }

        if (fault == "PRESSURE_OUT_OF_RANGE")
        {
            pressure = 0.9;
        }

        return (Math.Round(temperature, 2), Math.Round(pressure, 5));
    }
}
