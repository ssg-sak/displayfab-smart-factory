using System.Text.Json.Serialization;

namespace DisplayFab.Proc01Simulator;

// FastAPI가 받는 JSON과 같은 키 이름이어야 한다.
// C# 필드는 PascalCase, JSON은 snake_case → JsonPropertyName으로 맞춘다.

public class EquipmentEvent
{
    [JsonPropertyName("equipment_id")]
    public string EquipmentId { get; set; } = "";

    [JsonPropertyName("event_type")]
    public string EventType { get; set; } = "PROCESS";

    [JsonPropertyName("lot_id")]
    public string? LotId { get; set; }

    [JsonPropertyName("panel_id")]
    public string? PanelId { get; set; }

    [JsonPropertyName("process_step")]
    public string? ProcessStep { get; set; }

    [JsonPropertyName("recipe_id")]
    public string? RecipeId { get; set; }

    [JsonPropertyName("equipment_status")]
    public string EquipmentStatus { get; set; } = "RUN";

    [JsonPropertyName("chamber_temperature")]
    public double? ChamberTemperature { get; set; }

    [JsonPropertyName("vacuum_pressure")]
    public double? VacuumPressure { get; set; }

    [JsonPropertyName("cycle_time_sec")]
    public double? CycleTimeSec { get; set; }

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = "";

    [JsonPropertyName("inspect_result")]
    public string? InspectResult { get; set; }
}
