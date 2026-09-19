using System.Text.Json;
using System.Text.Json.Serialization;

// Lesson 2: class = 데이터 상자.
// Python dict 대신, 필드를 정해 두고 JSON으로 직렬화한다.

class EquipmentEvent
{
    [JsonPropertyName("equipment_id")]
    public string EquipmentId { get; set; } = "";

    [JsonPropertyName("lot_id")]
    public string LotId { get; set; } = "";

    [JsonPropertyName("process_step")]
    public string ProcessStep { get; set; } = "";

    [JsonPropertyName("chamber_temperature")]
    public double ChamberTemperature { get; set; }
}

class Program
{
    static void Main()
    {
        var evt = new EquipmentEvent();
        evt.EquipmentId = "PROC-01";
        evt.LotId = "LOT-20260918-001";
        evt.ProcessStep = "EVAP";
        evt.ChamberTemperature = 118.4;

        string json = JsonSerializer.Serialize(evt, new JsonSerializerOptions { WriteIndented = true });
        Console.WriteLine(json);
    }
}
