using System.Net.Http.Json;

namespace DisplayFab.Proc01Simulator;

// Python의 httpx.Client + post() 에 해당한다.
// using 으로 감싸면 프로그램이 끝날 때 HttpClient를 정리한다.

public class EquipmentSimulator : IDisposable
{
    private readonly HttpClient _http;
    private readonly SensorGenerator _sensors = new();
    private readonly string _apiUrl;

    private readonly string _host;

    public EquipmentSimulator(string apiUrl)
    {
        _apiUrl = apiUrl.Contains("/api/events", StringComparison.Ordinal) ? apiUrl : apiUrl.TrimEnd('/') + "/api/events";
        _host = _apiUrl.Replace("/api/events", "");
        _http = new HttpClient();
        _http.Timeout = TimeSpan.FromSeconds(5);
    }

    public EquipmentEvent BuildHeartbeat(string equipmentId)
    {
        var evt = new EquipmentEvent();
        evt.EquipmentId = equipmentId;
        evt.EventType = "HEARTBEAT";
        evt.LotId = null;
        evt.PanelId = null;
        evt.ProcessStep = null;
        evt.EquipmentStatus = "IDLE";
        evt.Timestamp = DateTime.UtcNow.ToString("o");
        return evt;
    }

    public EquipmentEvent BuildProcessEvent(string fault)
    {
        var (temp, pressure) = _sensors.Next("RCP-OLED-A01", fault);

        var evt = new EquipmentEvent();
        evt.EquipmentId = fault == "UNKNOWN_EQUIPMENT" ? "EQ-UNKNOWN" : "PROC-01";
        evt.EventType = "PROCESS";
        evt.LotId = fault == "INVALID_LOT" ? "LOT-NOPE" : "LOT-20260918-001";
        evt.PanelId = "PNL-00001";
        evt.ProcessStep = "EVAP";
        evt.RecipeId = fault == "RECIPE_MISMATCH" ? "RCP-OLED-B01" : "RCP-OLED-A01";
        evt.EquipmentStatus = "RUN";
        evt.ChamberTemperature = temp;
        evt.VacuumPressure = pressure;
        evt.CycleTimeSec = 47.2;
        evt.Timestamp = DateTime.UtcNow.ToString("o");
        return evt;
    }

    // async/await = 네트워크 응답을 기다린다. Python client.post() 와 같다.
    public async Task<HttpResponseMessage> PostWithRetryAsync(EquipmentEvent payload)
    {
        Exception? last = null;

        for (int attempt = 1; attempt <= 3; attempt++)
        {
            try
            {
                HttpResponseMessage response = await _http.PostAsJsonAsync(_apiUrl, payload);
                return response;
            }
            catch (Exception ex) when (ex is HttpRequestException || ex is TaskCanceledException)
            {
                last = ex;
                Console.Error.WriteLine($"POST failed attempt={attempt}: {ex.Message}");
                await Task.Delay(300 * attempt);
            }
        }

        throw last ?? new InvalidOperationException("POST failed");
    }

    // 루프용. 호스트가 꺼져 있어도 프로세스를 죽이지 않고 다음 주기에 다시 붙는다.
    public async Task<(bool Ok, int Status, string Body, string? Error)> TryPostAsync(EquipmentEvent payload)
    {
        try
        {
            HttpResponseMessage response = await PostWithRetryAsync(payload);
            string body = await response.Content.ReadAsStringAsync();
            return (response.IsSuccessStatusCode, (int)response.StatusCode, body, null);
        }
        catch (Exception ex)
        {
            return (false, 0, "", ex.Message);
        }
    }

    public async Task<T?> GetJsonAsync<T>(string path)
    {
        return await _http.GetFromJsonAsync<T>(_host + path);
    }

    public async Task PostCommandAsync(object body)
    {
        await _http.PostAsJsonAsync(_host + "/api/commands", body);
    }

    public EquipmentEvent BuildDispatched(string equipmentId, string step, string lotId, string panelId, string recipeId)
    {
        var (temp, pressure) = _sensors.Next(recipeId, "");
        var evt = new EquipmentEvent();
        evt.EquipmentId = equipmentId;
        evt.EventType = "PROCESS";
        evt.LotId = lotId;
        evt.PanelId = panelId;
        evt.ProcessStep = step;
        evt.RecipeId = recipeId;
        evt.EquipmentStatus = "RUN";
        evt.ChamberTemperature = temp;
        evt.VacuumPressure = pressure;
        evt.CycleTimeSec = step switch
        {
            "CLEAN" => 18.0,
            "EVAP" => 46.0,
            "ENCAP" => 30.0,
            "PI" => 22.0,
            "LCD_CELL" => 40.0,
            "INSPECT" => 12.0,
            _ => null
        };
        evt.InspectResult = step == "INSPECT" ? "PASS" : null;
        evt.Timestamp = DateTime.UtcNow.ToString("o");
        return evt;
    }

    public void Dispose()
    {
        _http.Dispose();
    }
}
