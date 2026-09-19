using System.Text.Json;
using System.Text.Json.Serialization;
using DisplayFab.Proc01Simulator;

// 프로그램 시작점. Python의 if __name__ == "__main__" 과 같다.
//
//   dotnet run
//   dotnet run -- --heartbeat --loop
//   dotnet run -- --heartbeat --loop --drop-after 3
//   dotnet run -- --process
//   dotnet run -- --fault RECIPE_MISMATCH
//   dotnet run -- --run-line
//   dotnet run -- --run-line WO-...

class Program
{
    static readonly string[] AllEquipment = { "LOAD-01", "CLEAN-01", "PROC-01", "PROC-02", "ENC-01", "PI-01", "LCD-01", "INSPECT-01" };

    static async Task Main(string[] args)
    {
        string apiUrl = "http://127.0.0.1:8000/api/events";
        string fault = "";
        bool heartbeat = true;
        bool loop = false;
        bool process = false;
        bool allEq = false;
        bool runLine = false;
        string workOrderId = "";
        int intervalMs = 3000;
        int dropAfter = 0;
        var equipmentIds = new List<string> { "PROC-01" };

        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--heartbeat")
            {
                heartbeat = true;
            }
            else if (args[i] == "--process")
            {
                process = true;
                heartbeat = false;
            }
            else if (args[i] == "--loop")
            {
                loop = true;
            }
            else if (args[i] == "--all")
            {
                allEq = true;
            }
            else if (args[i] == "--fault" && i + 1 < args.Length)
            {
                fault = args[i + 1];
                process = true;
                heartbeat = false;
                i++;
            }
            else if (args[i] == "--api" && i + 1 < args.Length)
            {
                apiUrl = args[i + 1];
                i++;
            }
            else if (args[i] == "--interval" && i + 1 < args.Length)
            {
                intervalMs = int.Parse(args[i + 1]) * 1000;
                i++;
            }
            else if (args[i] == "--drop-after" && i + 1 < args.Length)
            {
                dropAfter = int.Parse(args[i + 1]);
                loop = true;
                i++;
            }
            else if (args[i] == "--equipment" && i + 1 < args.Length)
            {
                equipmentIds = args[i + 1].Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
                i++;
            }
            else if (args[i] == "--run-line")
            {
                runLine = true;
                heartbeat = false;
                if (i + 1 < args.Length && !args[i + 1].StartsWith("--", StringComparison.Ordinal))
                {
                    workOrderId = args[i + 1];
                    i++;
                }
            }
            else if (args[i] == "--help")
            {
                Console.WriteLine("dotnet run -- [--heartbeat] [--loop] [--all] [--drop-after N] [--interval SEC] [--equipment PROC-01]");
                Console.WriteLine("dotnet run -- --process");
                Console.WriteLine("dotnet run -- --fault RECIPE_MISMATCH");
                Console.WriteLine("dotnet run -- --run-line [WO-ID]");
                Console.WriteLine();
                Console.WriteLine("기본: HEARTBEAT 1건. LOT 없이 PROC-01 last_seen만 갱신한다.");
                Console.WriteLine("--loop        3초마다 계속 보낸다. 호스트가 꺼져도 죽지 않고 다시 붙는다.");
                Console.WriteLine("--drop-after  N번 보낸 뒤 침묵. 약 10초 후 Conn이 OFFLINE이 되어야 한다.");
                Console.WriteLine("--run-line    호스트 dispatch를 따라 지시 LOT를 끝까지 보고한다.");
                Console.WriteLine("호스트 timeout은 10초다. interval은 그보다 짧게 둔다.");
                return;
            }
        }

        if (allEq)
        {
            equipmentIds = AllEquipment.ToList();
        }

        using var simulator = new EquipmentSimulator(apiUrl);

        try
        {
            if (runLine)
            {
                await RunLine(simulator, workOrderId);
                return;
            }

            if (heartbeat && loop)
            {
                await RunHeartbeatLoop(simulator, equipmentIds, intervalMs, dropAfter);
                return;
            }

            if (process)
            {
                await PrepareHost(simulator, "RCP-OLED-A01");
                if (fault == "RECIPE_MISMATCH")
                {
                    await simulator.PostCommandAsync(new { command_type = "SELECT_RECIPE", equipment_id = "PROC-01", recipe_id = "RCP-OLED-B01" });
                }
            }

            EquipmentEvent evt = process
                ? simulator.BuildProcessEvent(fault)
                : simulator.BuildHeartbeat(equipmentIds[0]);

            await SendOnce(simulator, evt);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Simulator failed: {ex.Message}");
            Console.Error.WriteLine("FastAPI가 8000에서 켜져 있는지 확인하세요.");
            Environment.ExitCode = 1;
        }
    }

    static async Task RunHeartbeatLoop(
        EquipmentSimulator simulator,
        List<string> equipmentIds,
        int intervalMs,
        int dropAfter)
    {
        using var cts = new CancellationTokenSource();
        Console.CancelKeyPress += (sender, e) =>
        {
            e.Cancel = true;
            cts.Cancel();
        };

        Console.WriteLine($"heartbeat loop every {intervalMs / 1000}s  eq={string.Join(",", equipmentIds)}");
        Console.WriteLine("LOT 없이 last_seen만 갱신한다. Ctrl+C to stop.");
        if (dropAfter > 0)
        {
            Console.WriteLine($"drop-after {dropAfter}: 그 횟수 이후 침묵 → 호스트가 OFFLINE + COMMUNICATION_LOSS 를 띄워야 한다.");
        }

        int rounds = 0;
        bool wasDown = false;

        while (!cts.IsCancellationRequested)
        {
            foreach (string eqId in equipmentIds)
            {
                EquipmentEvent evt = simulator.BuildHeartbeat(eqId);
                var (ok, status, _, error) = await simulator.TryPostAsync(evt);
                if (ok)
                {
                    if (wasDown)
                    {
                        Console.WriteLine("reconnected — Conn should return ONLINE, COMMUNICATION_LOSS resolve");
                    }
                    wasDown = false;
                    Console.WriteLine($"{DateTime.UtcNow:HH:mm:ss} {eqId} HEARTBEAT HTTP {status}");
                }
                else
                {
                    wasDown = true;
                    Console.WriteLine($"{DateTime.UtcNow:HH:mm:ss} {eqId} HEARTBEAT host unreachable: {error}");
                }
            }

            rounds++;
            if (dropAfter > 0 && rounds >= dropAfter)
            {
                Console.WriteLine("heartbeat dropped. ~10초 뒤 Dashboard Conn이 OFFLINE인지 본다. Ctrl+C to stop.");
                try
                {
                    await Task.Delay(Timeout.Infinite, cts.Token);
                }
                catch (TaskCanceledException)
                {
                    break;
                }
            }

            try
            {
                await Task.Delay(intervalMs, cts.Token);
            }
            catch (TaskCanceledException)
            {
                break;
            }
        }

        Console.WriteLine("heartbeat stopped.");
    }

    static async Task PrepareHost(EquipmentSimulator simulator, string recipeId)
    {
        foreach (string eq in AllEquipment)
        {
            await simulator.PostCommandAsync(new { command_type = "START", equipment_id = eq });
        }
        string[] recipeEq = recipeId.StartsWith("RCP-LCD", StringComparison.Ordinal)
            ? new[] { "PI-01", "LCD-01" }
            : new[] { "CLEAN-01", "PROC-01", "PROC-02", "ENC-01" };
        foreach (string eq in recipeEq)
        {
            await simulator.PostCommandAsync(new { command_type = "SELECT_RECIPE", equipment_id = eq, recipe_id = recipeId });
        }
    }

    static async Task RunLine(EquipmentSimulator simulator, string workOrderId)
    {
        List<WorkOrderInfo>? orders = await simulator.GetJsonAsync<List<WorkOrderInfo>>("/api/work-orders");
        if (orders == null || orders.Count == 0)
        {
            Console.WriteLine("지시가 없다. Ops Console에서 먼저 투입한다.");
            return;
        }

        WorkOrderInfo? wo = string.IsNullOrWhiteSpace(workOrderId)
            ? orders[0]
            : orders.Find(row => row.Id == workOrderId);
        if (wo == null || string.IsNullOrWhiteSpace(wo.LotId))
        {
            Console.WriteLine($"지시 없음: {workOrderId}");
            return;
        }

        Console.WriteLine($"run-line {wo.Id} lot={wo.LotId} recipe={wo.RecipeId}");
        await PrepareHost(simulator, wo.RecipeId);
        DateTime lastBeat = DateTime.MinValue;
        for (int i = 0; i < 80; i++)
        {
            lastBeat = await KeepAlive(simulator, lastBeat);
            DispatchInfo? info = await simulator.GetJsonAsync<DispatchInfo>($"/api/lots/{wo.LotId}/dispatch");
            if (info == null)
            {
                Console.WriteLine("dispatch 실패");
                return;
            }
            if (info.LotStatus == "HOLD")
            {
                Console.WriteLine($"HOLD {info.LotId} stop");
                return;
            }
            if (info.Done || string.IsNullOrWhiteSpace(info.NextStep) || string.IsNullOrWhiteSpace(info.NextEquipmentId))
            {
                Console.WriteLine($"done panel={info.PanelId} status={info.PanelStatus}");
                return;
            }

            EquipmentEvent evt = simulator.BuildDispatched(
                info.NextEquipmentId,
                info.NextStep,
                info.LotId,
                info.PanelId,
                wo.RecipeId);
            var (ok, status, body, error) = await simulator.TryPostAsync(evt);
            Console.WriteLine($"{DateTime.UtcNow:HH:mm:ss} {info.NextEquipmentId} {info.NextStep} {info.PanelId} HTTP {status}");
            if (!ok)
            {
                Console.WriteLine(error ?? body);
                return;
            }
            Console.WriteLine(body);
            await Task.Delay(200);
        }
    }

    // 라인을 돌리는 동안에도 설비는 살아 있다고 계속 알린다.
    // 보고가 5초 넘게 끊기면 호스트가 통신 끊김으로 보고 실적을 거절한다.
    static async Task<DateTime> KeepAlive(EquipmentSimulator simulator, DateTime lastBeat)
    {
        if ((DateTime.UtcNow - lastBeat).TotalSeconds < 5)
        {
            return lastBeat;
        }
        foreach (string eq in AllEquipment)
        {
            EquipmentEvent beat = simulator.BuildHeartbeat(eq);
            // 호스트가 켠 설비다. 생존신호로 대기 상태로 되돌리지 않는다.
            beat.EquipmentStatus = "RUN";
            await simulator.TryPostAsync(beat);
        }
        return DateTime.UtcNow;
    }

    static async Task SendOnce(EquipmentSimulator simulator, EquipmentEvent evt)
    {
        Console.WriteLine(JsonSerializer.Serialize(evt, new JsonSerializerOptions { WriteIndented = true }));
        HttpResponseMessage response = await simulator.PostWithRetryAsync(evt);
        string body = await response.Content.ReadAsStringAsync();
        Console.WriteLine($"HTTP {(int)response.StatusCode} {response.StatusCode}");
        Console.WriteLine(body);
    }
}

class WorkOrderInfo
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("lot_id")]
    public string? LotId { get; set; }

    [JsonPropertyName("recipe_id")]
    public string RecipeId { get; set; } = "";
}

class DispatchInfo
{
    [JsonPropertyName("panel_id")]
    public string PanelId { get; set; } = "";

    [JsonPropertyName("lot_id")]
    public string LotId { get; set; } = "";

    [JsonPropertyName("lot_status")]
    public string LotStatus { get; set; } = "";

    [JsonPropertyName("panel_status")]
    public string PanelStatus { get; set; } = "";

    [JsonPropertyName("next_step")]
    public string? NextStep { get; set; }

    [JsonPropertyName("next_equipment_id")]
    public string? NextEquipmentId { get; set; }

    [JsonPropertyName("done")]
    public bool Done { get; set; }
}
