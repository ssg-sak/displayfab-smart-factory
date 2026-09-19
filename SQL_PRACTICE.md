# SQL 연습

같은 질문을 SQLAlchemy ORM(`backend/app/services/sql_queries.py`)과 순수 SQL로 비교한다.

실행 예:

```text
docker compose up -d
docker exec -it displayfab-postgres psql -U displayfab -d displayfab
```

날짜는 UTC naive timestamp 기준이다.

---

## 1. 오늘 Alarm이 가장 많이 발생한 Equipment

ORM: `equipment_with_most_alarms_today()`

```sql
SELECT equipment_id, COUNT(*) AS alarm_count
FROM alarm
WHERE equipment_id IS NOT NULL
  AND occurred_at::date = CURRENT_DATE
GROUP BY equipment_id
ORDER BY alarm_count DESC;
```

---

## 2. 특정 LOT의 전체 공정이력

ORM: `lot_history(db, lot_id)`

```sql
SELECT event_timestamp, equipment_id, panel_id, process_step, recipe_id, cycle_time_sec
FROM process_event
WHERE lot_id = 'LOT-20260918-001'
ORDER BY event_timestamp, id;
```

---

## 3. 특정 Panel의 전체 이력

```sql
SELECT event_timestamp, equipment_id, process_step, recipe_id, inspect_result
FROM process_event
WHERE panel_id = 'PNL-00001'
ORDER BY event_timestamp, id;
```

---

## 4. 평균 Cycle Time이 가장 긴 Equipment

ORM: `avg_cycle_time_by_equipment()`

```sql
SELECT equipment_id, AVG(cycle_time_sec) AS avg_cycle
FROM process_event
WHERE cycle_time_sec IS NOT NULL
GROUP BY equipment_id
ORDER BY avg_cycle DESC;
```

---

## 5. RECIPE_MISMATCH가 발생한 LOT

ORM: `lots_with_recipe_mismatch()`

```sql
SELECT DISTINCT lot_id
FROM alarm
WHERE alarm_code = 'RECIPE_MISMATCH'
  AND lot_id IS NOT NULL;
```

---

## 6. 최근 1시간 동안 OFFLINE이 있었던 Equipment

ORM: `offline_equipment_last_hour()`

```sql
SELECT DISTINCT equipment_id
FROM alarm
WHERE alarm_code = 'COMMUNICATION_LOSS'
  AND occurred_at >= NOW() - INTERVAL '1 hour'
  AND equipment_id IS NOT NULL

UNION

SELECT id
FROM equipment
WHERE connection_status = 'OFFLINE';
```

---

## 7. HOLD 상태인 LOT

```sql
SELECT id, current_equipment_id, current_step, hold_reason
FROM lot
WHERE status = 'HOLD';
```

---

## 8. 설비별 생산 Panel 수

```sql
SELECT equipment_id, COUNT(DISTINCT panel_id) AS panel_count
FROM process_event
GROUP BY equipment_id;
```

---

## 9. Recipe별 평균 Cycle Time

```sql
SELECT recipe_id, AVG(cycle_time_sec) AS avg_cycle
FROM process_event
WHERE recipe_id IS NOT NULL
  AND cycle_time_sec IS NOT NULL
GROUP BY recipe_id;
```

---

## 10. 특정 설비의 최근 20개 Event

```sql
SELECT event_timestamp, lot_id, panel_id, process_step, recipe_id
FROM process_event
WHERE equipment_id = 'PROC-01'
ORDER BY event_timestamp DESC
LIMIT 20;
```

---

## ORM vs SQL을 같이 적어 둔 이유

같은 질문을 ORM과 순수 SQL로 같이 적어 둔 이유: 추상화가 달라도 테이블과 질문은 같다.

- 순수 SQL: 인덱스와 GROUP BY를 말로 설명하기 쉽다.
- ORM: FastAPI 서비스에서 재사용하고 테스트를 붙이기 쉽다.

둘 다 같은 테이블을 본다. 추상화가 달라도 질문(오늘 어느 설비가 많이 멈췄는가)은 같다.
