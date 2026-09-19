-- DisplayFab Ops Lab — interview SQL
-- PostgreSQL. 실제 MES 쿼리가 아니다.
--
--   docker compose up -d
--   docker exec -it displayfab-postgres psql -U displayfab -d displayfab
--
-- 시각 컬럼은 UTC naive timestamp로 저장한다.
-- 그래서 현재시각은 NOW() AT TIME ZONE 'UTC' 로 맞춘다.

-- 1. 오늘 Alarm이 가장 많이 발생한 Equipment
SELECT equipment_id, COUNT(*) AS alarm_count
FROM alarm
WHERE equipment_id IS NOT NULL
  AND occurred_at::date = (NOW() AT TIME ZONE 'UTC')::date
GROUP BY equipment_id
ORDER BY alarm_count DESC;

-- 2. 특정 LOT의 전체 공정이력
SELECT event_timestamp, equipment_id, panel_id, process_step, recipe_id, cycle_time_sec
FROM process_event
WHERE lot_id = 'LOT-20260918-001'
ORDER BY event_timestamp, id;

-- 3. 특정 Panel의 전체 이력
SELECT event_timestamp, equipment_id, process_step, recipe_id, inspect_result
FROM process_event
WHERE panel_id = 'PNL-00001'
ORDER BY event_timestamp, id;

-- 4. 평균 Cycle Time이 가장 긴 Equipment
SELECT equipment_id, AVG(cycle_time_sec) AS avg_cycle
FROM process_event
WHERE cycle_time_sec IS NOT NULL
GROUP BY equipment_id
ORDER BY avg_cycle DESC;

-- 5. RECIPE_MISMATCH가 발생한 LOT
SELECT DISTINCT lot_id
FROM alarm
WHERE alarm_code = 'RECIPE_MISMATCH'
  AND lot_id IS NOT NULL;

-- 6. 최근 1시간 동안 OFFLINE이 있었던 Equipment
SELECT DISTINCT equipment_id
FROM alarm
WHERE alarm_code = 'COMMUNICATION_LOSS'
  AND occurred_at >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '1 hour'
  AND equipment_id IS NOT NULL
UNION
SELECT id
FROM equipment
WHERE connection_status = 'OFFLINE';

-- 7. HOLD 상태인 LOT
SELECT id, current_equipment_id, current_step, hold_reason
FROM lot
WHERE status = 'HOLD';

-- 8. 설비별 생산 Panel 수
SELECT equipment_id, COUNT(DISTINCT panel_id) AS panel_count
FROM process_event
GROUP BY equipment_id;

-- 9. Recipe별 평균 Cycle Time
SELECT recipe_id, AVG(cycle_time_sec) AS avg_cycle
FROM process_event
WHERE recipe_id IS NOT NULL
  AND cycle_time_sec IS NOT NULL
GROUP BY recipe_id;

-- 10. 특정 설비의 최근 20개 Event
SELECT event_timestamp, lot_id, panel_id, process_step, recipe_id
FROM process_event
WHERE equipment_id = 'PROC-01'
ORDER BY event_timestamp DESC
LIMIT 20;

-- 11. 설비별 마지막 수신 Telemetry (인터페이스 계층)
SELECT DISTINCT ON (equipment_id)
       equipment_id, interface_type, source,
       chamber_temperature, vacuum_pressure, recorded_at
FROM telemetry
ORDER BY equipment_id, recorded_at DESC, id DESC;

-- 12. 설비별 누적 정지시간 (OEE Availability 재료)
SELECT equipment_id,
       reason,
       COUNT(*) AS occurrences,
       SUM(
         COALESCE(
           duration_sec,
           EXTRACT(EPOCH FROM ((NOW() AT TIME ZONE 'UTC') - started_at))
         )
       ) AS downtime_sec
FROM equipment_downtime
GROUP BY equipment_id, reason
ORDER BY downtime_sec DESC;
