# Equipment Adapter

현재 공장 통신은 **HTTP JSON push** 다. OPC UA / Modbus 실체는 없다.

```text
                 EquipmentAdapter
                        │
        ┌───────────────┼────────────────┐
        ↓               ↓                ↓
SimulatorAdapter   OPCUAAdapter     ModbusAdapter
   사용 중           TODO              TODO
```

살아 있는 클라이언트:

- `simulator/python_simulator.py`
- `csharp_simulator/`

수집:

```text
POST /api/events
    → collector.collect_push
    → SimulatorAdapter.accept_push  (telemetry 테이블)
    → ingest_event                  (MES / 검증 / process_event)
```

명령:

```text
POST /api/commands
    → execute_command
    → Adapter.send_command
```

조회:

- `GET /api/equipment/{id}/interface`
- `GET /api/equipment/{id}/telemetry`
- `GET /api/equipment/{id}/downtime`

Analytics가 Adapter를 직접 부르지 않는다.
