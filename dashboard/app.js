async function getJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(path + " " + res.status);
  return res.json();
}

const KO = {
  step: {
    LOAD: "투입",
    CLEAN: "세정",
    EVAP: "증착",
    ENCAP: "봉지",
    PI: "배향막",
    LCD_CELL: "셀 공정",
    INSPECT: "검사",
    COMPLETE: "완료",
    FAIL: "불량",
    SCRAP: "폐기",
  },
  status: {
    RUN: "가동 중",
    IDLE: "대기",
    STOP: "정지",
    ERROR: "이상",
    MAINTENANCE: "정비",
    PROCESSING: "진행 중",
    HOLD: "보류",
    WAIT: "대기",
    COMPLETE: "완료",
    FAIL: "불량",
    SCRAP: "폐기",
    RELEASED: "투입됨",
    DONE: "끝",
    PLANNED: "계획",
    PASS: "합격",
  },
  conn: {
    ONLINE: "연결됨",
    OFFLINE: "끊김",
  },
  iface: {
    simulator: "가상 설비",
    opcua: "OPC UA",
    modbus: "모드버스",
  },
  cmd: {
    START: "가동",
    STOP: "정지",
    SELECT_RECIPE: "조건 고르기",
    HOLD_LOT: "작업 보류",
    RELEASE_LOT: "보류 해제",
    MAINT_ENTER: "정비 시작",
    MAINT_EXIT: "정비 끝",
    ACK_ALARM: "알람 확인",
    SCRAP_PANEL: "유리 폐기",
  },
  cmdStatus: {
    ACCEPTED: "수락",
    REJECTED: "거절",
    COMPLETED: "완료",
  },
  alarm: {
    COMMUNICATION_LOSS: "통신 끊김",
    TEMPERATURE_OUT_OF_RANGE: "온도 벗어남",
    PRESSURE_OUT_OF_RANGE: "압력 벗어남",
    RECIPE_MISMATCH: "조건 불일치",
    RECIPE_NOT_SELECTED: "조건 미선택",
    INVALID_LOT: "없는 작업묶음",
    INVALID_PANEL: "유리 불일치",
    DUPLICATE_EVENT: "중복 보고",
    STALE_TIMESTAMP: "오래된 시각",
    UNKNOWN_EQUIPMENT: "없는 설비",
    DB_WRITE_FAILURE: "저장 실패",
    INTERLOCK_VIOLATION: "인터록",
    STEP_SEQUENCE_VIOLATION: "공정 순서 오류",
    PRODUCT_ROUTE_VIOLATION: "제품 경로 오류",
    EQUIPMENT_BUSY: "설비 사용 중",
    EQUIPMENT_MAINTENANCE: "정비 중",
    EQUIPMENT_STOPPED: "정지됨 · 가동 필요",
    ILLEGAL_STATE_TRANSITION: "상태 전환 오류",
    INSPECT_FAIL: "검사 불량",
    HOST_HOLD: "호스트가 멈춤",
    STOP: "정지",
    MAINTENANCE: "정비",
  },
  severity: {
    CRITICAL: "심각",
    WARNING: "경고",
    INFO: "안내",
  },
  recipe: {
    "RCP-OLED-A01": "올레드 가",
    "RCP-OLED-B01": "올레드 나",
    "RCP-LCD-C01": "엘시디 다",
  },
  eqName: {
    "LOAD-01": "투입",
    "CLEAN-01": "세정",
    "PROC-01": "증착 1호기",
    "PROC-02": "증착 2호기",
    "ENC-01": "봉지",
    "PI-01": "배향막",
    "LCD-01": "셀 공정",
    "INSPECT-01": "검사",
  },
  event: {
    PROCESS: "실적",
    HEARTBEAT: "생존신호",
  },
};

function ko(map, key) {
  if (key == null || key === "") return "-";
  return map[key] || key;
}

function koProduct(key) {
  if (key === "OLED") return "올레드";
  if (key === "LCD") return "엘시디";
  return key || "";
}

function koEq(id) {
  return KO.eqName[id] || id || "";
}

function koInterface(key) {
  return ko(KO.iface, key);
}

function koCassetteLabel(cst) {
  const raw = String((cst && (cst.cassette_id || cst.lot_id)) || "");
  const product = koProduct(cst && cst.product_type);
  let num = raw.replace(/^CST-/, "").replace(/^OLED-/, "").replace(/^LCD-/, "").replace(/^LOT-/, "");
  num = num.replace(/^0+/, "") || num;
  if (product && num) return product + " " + num;
  return product || num || "-";
}

function koText(text) {
  if (text == null || text === "") return "";
  let s = String(text);
  Object.keys(KO.eqName).forEach(function (id) {
    s = s.split(id).join(KO.eqName[id]);
  });
  Object.keys(KO.recipe).forEach(function (id) {
    s = s.split(id).join(KO.recipe[id]);
  });
  s = s.replace(/\bOLED\b/g, "올레드");
  s = s.replace(/\bLCD\b/g, "엘시디");
  s = s.replace(/\bRecipe\b/g, "조건");
  s = s.replace(/\bPPID=/g, "조건 ");
  s = s.replace(/\bPPID\b/g, "조건");
  s = s.replace(/\bINSPECT FAIL\b/g, "검사 불량");
  s = s.replace(/\bOLED lot\b/g, "올레드 작업");
  s = s.replace(/\bLCD lot\b/g, "엘시디 작업");
  s = s.replace(/\bHOLD\b/g, "보류");
  s = s.replace(/\bRELEASE\b/g, "다시 보내기");
  s = s.replace(/\bSCRAP_PANEL\b/g, "버리기");
  s = s.replace(/\bSCRAP\b/g, "폐기");
  s = s.replace(/\bFAIL\b/g, "불량");
  s = s.replace(/\bCOMPLETE\b/g, "완료");
  s = s.replace(/\bMAINTENANCE\b/g, "정비");
  s = s.replace(/\bOFFLINE\b/g, "끊김");
  s = s.replace(/\bONLINE\b/g, "연결");
  s = s.replace(/\bRUN\b/g, "가동");
  s = s.replace(/\bSTOP\b/g, "정지");
  s = s.replace(/\bIDLE\b/g, "대기");
  s = s.replace(/\bWAIT\b/g, "대기");
  s = s.replace(/\bCassette\b/g, "카세트");
  s = s.replace(/\bGlass\b/g, "유리");
  s = s.replace(/\bAlarm\b/g, "알람");
  s = s.replace(/\bevent_log\b/g, "보고 기록");
  s = s.replace(/LOT not found/g, "작업이 없습니다");
  s = s.replace(/Equipment not found/g, "설비가 없습니다");
  s = s.replace(/recipe_id required/g, "조건을 고르세요");
  s = s.replace(/Cannot START\/STOP during 정비/g, "정비 중에는 켜거나 끌 수 없습니다");
  s = s.replace(/Cannot START\/STOP during MAINTENANCE/g, "정비 중에는 켜거나 끌 수 없습니다");
  s = s.replace(/완료 LOT cannot 보류/g, "끝난 작업은 멈출 수 없습니다");
  s = s.replace(/already 폐기/g, "이미 버린 유리입니다");
  s = s.replace(/is 완료/g, "이미 끝났습니다");
  s = s.replace(/acknowledged/g, "확인함");
  s = s.replace(/released/g, "다시 보냄");
  s = s.replace(/보류 by host/g, "호스트가 멈춤");
  s = s.replace(/Alarm not found/g, "알람이 없습니다");
  s = s.replace(/Panel not found/g, "유리가 없습니다");
  s = s.replace(/Unsupported command /g, "없는 명령 ");
  s = s.replace(/scope=/g, "제품=");
  s = s.replace(/recipe=/g, "조건=");
  return s;
}

function koStep(key) {
  return ko(KO.step, key);
}

function koStatus(key) {
  return ko(KO.status, key);
}

function koRecipe(key) {
  if (!key) return "없음";
  return KO.recipe[key] || key;
}

function alarmSay(row) {
  const machine = KO.eqName[row.equipment_id] || row.equipment_id || "기계";
  const job = row.lot_id || "";
  const code = row.alarm_code;
  if (code === "COMMUNICATION_LOSS") return machine + "에서 신호가 안 옵니다. 줄이 끊겼습니다.";
  if (code === "EQUIPMENT_BUSY") return machine + "이 다른 유리를 돌리는 중입니다.";
  if (code === "STEP_SEQUENCE_VIOLATION") return "순서가 틀렸습니다. " + (job ? job + " 유리는 " : "") + "지금 이 기계에 들어가면 안 됩니다.";
  if (code === "PRODUCT_ROUTE_VIOLATION") return "제품이 다른 라인 기계에 들어갔습니다.";
  if (code === "RECIPE_MISMATCH") return "조건이 안 맞습니다.";
  if (code === "RECIPE_NOT_SELECTED") return machine + "에 조건을 아직 안 골랐습니다.";
  if (code === "EQUIPMENT_STOPPED") return machine + "이 꺼져 있습니다. 먼저 켜세요.";
  if (code === "EQUIPMENT_MAINTENANCE") return machine + "을 고치는 중입니다.";
  if (code === "INSPECT_FAIL") return "검사에서 불량이 나왔습니다.";
  if (code === "TEMPERATURE_OUT_OF_RANGE") return machine + " 온도가 범위를 벗어났습니다.";
  if (code === "PRESSURE_OUT_OF_RANGE") return machine + " 압력이 범위를 벗어났습니다.";
  if (code === "INTERLOCK_VIOLATION") return "지금은 그 작업을 하면 안 됩니다.";
  if (code === "PANEL_SCRAPPED") return "이미 버린 유리입니다.";
  if (code === "DUPLICATE_EVENT") return "같은 보고가 또 들어왔습니다.";
  if (code === "STALE_TIMESTAMP") return "너무 오래된 보고입니다.";
  if (code === "UNKNOWN_EQUIPMENT") return "없는 기계입니다.";
  if (code === "INVALID_LOT") return "없는 작업입니다.";
  if (code === "INVALID_PANEL") return "유리가 그 작업에 없습니다.";
  return ko(KO.alarm, code);
}

function cell(text, cls) {
  const td = document.createElement("td");
  td.textContent = text == null ? "-" : text;
  if (cls) td.className = cls;
  return td;
}

function chamberState(row) {
  if (!row) return { text: "없음", cls: "STOP" };
  if (row.connection_status === "OFFLINE") return { text: "줄이 끊김", cls: "OFFLINE" };
  if (row.equipment_status === "RUN") return { text: "가동 중", cls: "RUN" };
  if (row.equipment_status === "IDLE") return { text: "대기", cls: "IDLE" };
  if (row.equipment_status === "MAINTENANCE") return { text: "정비", cls: "MAINTENANCE" };
  if (row.equipment_status === "STOP") return { text: "정지", cls: "STOP" };
  return { text: koStatus(row.equipment_status), cls: row.equipment_status };
}

function makeToken(cst) {
  const el = document.createElement("span");
  const product = cst.product_type || "";
  el.className = "glass-sheet token " + product + " " + (cst.status || "");
  el.title = (cst.lot_id || "") + " · " + (cst.cassette_id || "");
  const face = document.createElement("span");
  face.className = "panel-face " + (product === "LCD" ? "lcd-face" : "oled-face");
  const lab = document.createElement("span");
  lab.textContent = koCassetteLabel(cst);
  el.appendChild(face);
  el.appendChild(lab);
  return el;
}

function tokensOnEquipment(eqId, eqRow, cassettes) {
  if (!eqRow || !eqRow.current_lot_id) return [];
  const found = (cassettes || []).find(function (c) { return c.lot_id === eqRow.current_lot_id; });
  return [
    found || {
      lot_id: eqRow.current_lot_id,
      cassette_id: eqRow.current_lot_id,
      product_type: eqRow.product_scope || "",
      status: "PROCESSING",
    },
  ];
}

function waitingCassettes(cassettes, eqRows) {
  const busy = {};
  (eqRows || []).forEach(function (row) {
    if (row.current_lot_id) busy[row.current_lot_id] = true;
  });
  return (cassettes || []).filter(function (c) {
    return c.next_step && !busy[c.lot_id];
  });
}

function finishedCassettes(cassettes) {
  return (cassettes || []).filter(function (c) {
    return !c.next_step && c.status !== "HOLD";
  });
}

function startEquipmentMonitor() {
  const tbody = document.getElementById("rows");
  async function refresh() {
    const rows = await getJson("/api/equipment");
    tbody.innerHTML = "";
    for (const row of rows) {
      const tr = document.createElement("tr");
      tr.appendChild(cell(row.id));
      tr.appendChild(cell(koStatus(row.equipment_status), row.equipment_status));
      tr.appendChild(cell(ko(KO.conn, row.connection_status), row.connection_status));
      tr.appendChild(cell(row.current_lot_id));
      tr.appendChild(cell(koRecipe(row.current_recipe_id)));
      tr.appendChild(cell(row.last_seen_at));
      tr.appendChild(cell(row.open_alarm_count));
      tbody.appendChild(tr);
    }
  }
  refresh();
  setInterval(refresh, 2000);
}

function startLotMonitor() {
  const tbody = document.getElementById("rows");
  const board = document.getElementById("lotBoard");
  async function refresh() {
    const rows = await getJson("/api/lots");
    tbody.innerHTML = "";
    if (board) board.innerHTML = "";
    for (const row of rows) {
      const tr = document.createElement("tr");
      tr.appendChild(cell(row.id));
      tr.appendChild(cell(row.cassette_id));
      tr.appendChild(cell(koProduct(row.product_type)));
      tr.appendChild(cell(koStep(row.current_step)));
      tr.appendChild(cell(koStatus(row.status), row.status));
      tr.appendChild(cell(row.current_equipment_id));
      tr.appendChild(cell(koRecipe(row.expected_recipe_id)));
      tr.appendChild(cell(row.panel_count));
      tr.appendChild(cell(ko(KO.alarm, row.hold_reason)));
      tbody.appendChild(tr);
      if (!board) continue;
      const card = document.createElement("article");
      card.className = "lot-card " + row.status;
      card.innerHTML =
        "<h3>" + koCassetteLabel(row) + " · " + koProduct(row.product_type) + "</h3>" +
        "<p>" + koStatus(row.status) + " · " + (row.current_step ? koStep(row.current_step) : "대기") +
        (row.current_equipment_id ? " · " + (KO.eqName[row.current_equipment_id] || row.current_equipment_id) : "") +
        "</p>";
      card.appendChild(makeToken(row));
      card.addEventListener("click", function () {
        const input = document.getElementById("slotLot");
        if (input) input.value = row.id;
        const form = document.getElementById("slotForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
      board.appendChild(card);
    }
  }
  refresh();
  setInterval(refresh, 2000);
}

function startSlotMap() {
  const form = document.getElementById("slotForm");
  const out = document.getElementById("slotOut");
  const wells = document.getElementById("cassetteWells");
  const pathBox = document.getElementById("travelerPath");
  async function lookup(lotId) {
    if (!lotId) return;
    const [data, traveler] = await Promise.all([
      getJson("/api/lots/" + encodeURIComponent(lotId) + "/slots"),
      getJson("/api/lots/" + encodeURIComponent(lotId) + "/traveler"),
    ]);
    const lines = (data.slots || []).map(function (s) {
      return "칸 " + s.slot_no + "  ·  " + s.panel_id + "  ·  " + koStatus(s.status);
    });
    const path = (traveler.slots || []).map(function (s) {
      return (
        "칸 " + s.slot_no + "  ·  " + s.panel_id + "  ·  " + koStatus(s.status) +
        "  ·  마지막 " + koStep(s.last_step) + " @ " + (s.last_equipment_id || "-")
      );
    });
    if (out) {
      out.textContent = [
        data.cassette_id + "  ·  " + data.product_type + "  ·  " + koStatus(data.status),
        lines.join("\n"),
        "",
        "지금 공정  " + koStep(traveler.current_step) + "  ·  설비 " + (traveler.current_equipment_id || "-"),
        path.join("\n"),
      ].join("\n");
    }
    if (wells) {
      wells.innerHTML = "";
      (traveler.slots || data.slots || []).forEach(function (s) {
        const well = document.createElement("div");
        well.className = "well glass " + (s.status || "");
        well.innerHTML =
          "<b>칸 " + s.slot_no + "</b><span>" + (s.panel_id || "-") + "</span>" +
          "<span class=\"" + (s.status || "") + "\">" + koStatus(s.status) + "</span>" +
          "<span>" + (s.last_step ? koStep(s.last_step) : "아직 없음") + "</span>";
        wells.appendChild(well);
      });
    }
    if (pathBox) {
      pathBox.innerHTML = "";
      const here = traveler.current_step;
      const route = traveler.product_type === "LCD"
        ? ["LOAD", "PI", "LCD_CELL", "INSPECT"]
        : ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"];
      const last = (traveler.slots || []).map(function (s) { return s.last_step; });
      route.forEach(function (step) {
        const box = document.createElement("div");
        const done = last.indexOf(step) >= 0;
        box.className = "path-step" + (step === here ? " now" : done ? " done" : "");
        box.innerHTML = "<b>" + koStep(step) + "</b><span>" + (step === here ? "지금" : done ? "지남" : "앞") + "</span>";
        pathBox.appendChild(box);
      });
    }
  }
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    lookup(document.getElementById("slotLot").value.trim());
  });
  lookup(document.getElementById("slotLot").value.trim());
}

async function refreshAnomaly() {
  const rowsEl = document.getElementById("anomalyRows");
  const noteEl = document.getElementById("anomalyNote");
  if (!rowsEl) return;
  const data = await getJson("/api/analytics/anomaly");
  if (noteEl) {
    const flagged = data.flagged && data.flagged.length
      ? "볼 것: " + data.flagged.map(koEq).join(", ")
      : "지금 튀는 값 없음";
    noteEl.textContent = flagged + "  ·  " + data.method + "  ·  " + data.note;
  }
  rowsEl.innerHTML = "";
  (data.equipment || []).forEach(function (row) {
    const tr = document.createElement("tr");
    const cls = row.level === "경보" ? "CRITICAL" : (row.level === "주의" ? "HOLD" : "");
    tr.appendChild(cell(KO.eqName[row.equipment_id] || row.equipment_id));
    tr.appendChild(cell(row.samples));
    tr.appendChild(cell(row.temperature ? row.temperature.latest : null));
    tr.appendChild(cell(row.temperature ? row.temperature.sigma : null, cls));
    tr.appendChild(cell(row.pressure ? row.pressure.latest : null));
    tr.appendChild(cell(row.pressure ? row.pressure.sigma : null, cls));
    tr.appendChild(cell(row.level, cls));
    rowsEl.appendChild(tr);
  });
}

function startAlarmMonitor() {
  const box = document.getElementById("alarmList");
  const line = document.getElementById("alarmLine");
  async function refresh() {
    const [rows, eq] = await Promise.all([
      getJson("/api/alarms"),
      getJson("/api/equipment"),
    ]);
    if (line) {
      line.innerHTML = "";
      const openByEq = {};
      rows.forEach(function (row) {
        if (row.resolved_at || !row.equipment_id) return;
        openByEq[row.equipment_id] = (openByEq[row.equipment_id] || 0) + 1;
      });
      eq.forEach(function (row) {
        const st = chamberState(row);
        const mini = document.createElement("div");
        mini.className = "mini-chamber " + st.cls;
        const n = openByEq[row.id] || 0;
        mini.innerHTML =
          "<h3>" + (KO.eqName[row.id] || row.id) + "</h3>" +
          "<span class=\"" + st.cls + "\">" + st.text + "</span>" +
          "<span>" + (n ? "알람 " + n : "정상") + "</span>";
        line.appendChild(mini);
      });
    }
    await refreshAnomaly();
    box.innerHTML = "";
    if (!rows.length) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = "알람이 없습니다.";
      box.appendChild(p);
      return;
    }
    for (const row of rows) {
      const card = document.createElement("div");
      card.className = "alarm-card";
      const title = document.createElement("h3");
      title.textContent = ko(KO.alarm, row.alarm_code);
      title.className = row.severity;
      card.appendChild(title);
      const who = document.createElement("p");
      who.textContent = [
        KO.eqName[row.equipment_id] || row.equipment_id || "기계 없음",
        row.lot_id ? "작업 " + row.lot_id : "",
        ko(KO.severity, row.severity),
        row.resolved_at ? "이미 봄" : "아직 안 봄",
      ].filter(Boolean).join("  ·  ");
      who.className = row.resolved_at ? "COMPLETE" : "HOLD";
      card.appendChild(who);
      const msg = document.createElement("p");
      msg.textContent = alarmSay(row);
      card.appendChild(msg);
      box.appendChild(card);
    }
  }
  refresh();
  setInterval(refresh, 2000);
}

function startTraceability() {
  const form = document.getElementById("search");
  const timeline = document.getElementById("timeline");
  const empty = document.getElementById("empty");
  const pathBox = document.getElementById("glassPath");

  async function lookup(panelId) {
    timeline.innerHTML = "";
    empty.textContent = "";
    if (pathBox) pathBox.innerHTML = "";
    const res = await fetch("/api/panels/" + encodeURIComponent(panelId) + "/history");
    if (res.status === 404) {
      empty.textContent = "없는 유리 번호입니다.";
      return;
    }
    const rows = await res.json();
    if (!rows.length) {
      empty.textContent = "이력이 없습니다. 설비가 보고를 보냈는지 확인하세요.";
      return;
    }
    if (pathBox) {
      rows.forEach(function (row) {
        if (row.event_type && row.event_type !== "PROCESS") return;
        const box = document.createElement("div");
        box.className = "path-step done";
        box.innerHTML =
          "<b>" + koStep(row.process_step) + "</b><span>" +
          (KO.eqName[row.equipment_id] || row.equipment_id || "") +
          (row.inspect_result ? " · " + koStatus(row.inspect_result) : "") +
          "</span>";
        pathBox.appendChild(box);
      });
    }
    for (const row of rows) {
      const li = document.createElement("li");
      const inspect = row.inspect_result ? " · " + koStatus(row.inspect_result) : "";
      li.textContent = [
        ko(KO.eqName, row.equipment_id) + " (" + row.equipment_id + ")",
        row.event_timestamp,
        koStep(row.process_step),
        row.recipe_id ? koRecipe(row.recipe_id) : "",
        inspect,
      ].filter(Boolean).join("  ·  ");
      timeline.appendChild(li);
    }
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    lookup(document.getElementById("panelId").value.trim());
  });
  lookup(document.getElementById("panelId").value.trim());
}

function startOpsConsole() {
  const oledCards = document.getElementById("oledCards");
  const lcdCards = document.getElementById("lcdCards");
  const commonCards = document.getElementById("commonCards");
  const toolYield = document.getElementById("toolYield");
  const holdCards = document.getElementById("holdCards");
  const alarmCards = document.getElementById("alarmCards");
  const lotBody = document.getElementById("lotRows");
  const feed = document.getElementById("feed");
  const kpis = document.getElementById("kpis");
  const closeoutBox = document.getElementById("closeout");
  const cmdFeed = document.getElementById("cmdFeed");
  const productionBox = document.getElementById("production");
  const blockedBox = document.getElementById("blocked");
  const wipBox = document.getElementById("wip");
  const routes = document.getElementById("routes");
  const woRows = document.getElementById("woRows");
  const woOut = document.getElementById("woOut");
  const diagOut = document.getElementById("diagOut");
  const cmdResult = document.getElementById("cmdResult");
  let lastWoId = "";
  let lastHoldKey = "";
  const scenarioOut = document.getElementById("scenarioOut");
  const scenarioButtons = document.getElementById("scenarioButtons");
  const demoButtons = document.getElementById("demoButtons");
  const EQ_ORDER = ["LOAD-01", "CLEAN-01", "PROC-01", "PROC-02", "ENC-01", "PI-01", "LCD-01", "INSPECT-01"];
  let refreshing = false;
  let playing = false;

  function seenText(value) {
    if (!value) return "아직 없음";
    const text = String(value);
    const t = text.indexOf("T");
    return t > 0 ? text.slice(t + 1, t + 9) : text;
  }

  function addKpi(label, value, cls) {
    const box = document.createElement("div");
    box.className = "kpi";
    const lab = document.createElement("span");
    lab.textContent = label;
    const num = document.createElement("b");
    num.textContent = value == null ? "-" : value;
    if (cls) num.className = cls;
    box.appendChild(lab);
    box.appendChild(num);
    kpis.appendChild(box);
  }

  async function sendCommand(body) {
    const hint = document.getElementById("scenarioHint");
    if (hint) hint.textContent = (ko(KO.cmd, body.command_type) || "명령") + " 보내는 중…";
    try {
      const res = await fetch("/api/commands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const text = await res.text();
      try {
        const data = JSON.parse(text);
        const msg = ko(KO.cmd, data.command_type) + "  ·  " + ko(KO.cmdStatus, data.status) + "  ·  " + koText(data.message || "");
        cmdResult.textContent = msg;
        if (hint) hint.textContent = msg;
      } catch (err) {
        cmdResult.textContent = text;
        if (hint) hint.textContent = text;
      }
    } catch (err) {
      cmdResult.textContent = String(err);
      if (hint) hint.textContent = "명령을 못 보냈습니다. " + err;
    }
    await refresh();
  }

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  async function playRoute(product, label) {
    playing = true;
    const path = product === "LCD"
      ? ["LOAD-01", "PI-01", "LCD-01", "INSPECT-01"]
      : ["LOAD-01", "CLEAN-01", "PROC-01", "ENC-01", "INSPECT-01"];
    const hint = document.getElementById("scenarioHint");
    for (let i = 0; i < path.length; i += 1) {
      document.querySelectorAll(".glass-sheet.walk").forEach(function (node) { node.remove(); });
      const box = document.querySelector('.chamber[data-eq="' + path[i] + '"] .tokens');
      if (box) {
        const glass = makeToken({ product_type: product, cassette_id: label, status: "PROCESSING" });
        glass.classList.add("walk");
        box.appendChild(glass);
      }
      if (hint) hint.textContent = koProduct(product) + " 패널이 " + (KO.eqName[path[i]] || path[i]) + "를 지나는 중";
      await sleep(480);
    }
    playing = false;
  }

  async function showDiag(lotId) {
    document.getElementById("cmdLot").value = lotId;
    const data = await getJson("/api/lots/" + encodeURIComponent(lotId) + "/diagnosis");
    const alarms = (data.open_alarms || []).map(function (a) {
      return "- " + ko(KO.alarm, a.alarm_code) + "  " + koText(a.message || "");
    });
    diagOut.textContent = [
      koText(data.summary || ""),
      koText(data.action || ""),
      alarms.length ? "열린 알람\n" + alarms.join("\n") : "열린 알람 없음",
    ].join("\n");
  }

  function makeBtn(label, handler) {
    const el = document.createElement("button");
    el.type = "button";
    el.textContent = label;
    el.addEventListener("click", handler);
    return el;
  }

  function line(text, cls) {
    const p = document.createElement("p");
    p.textContent = text;
    if (cls) p.className = cls;
    return p;
  }

  function shortScenario(data) {
    if (!data) return "";
    if (data.seed_used === false) {
      return [
        data.ok ? "라인 돌림" : "라인 멈춤",
        "지시 " + (data.work_order_id || "-"),
        "작업묶음 " + (data.lot_id || "-"),
        "카세트 " + (data.cassette_id || "-"),
        "상태 " + koStatus(data.lot_status),
        data.hold_reason ? "이유 " + ko(KO.alarm, data.hold_reason) : "",
      ].filter(Boolean).join("  ·  ");
    }
    if (data.error) return "실패  ·  " + data.error;
    const results = data.results || [];
    const last = results[results.length - 1];
    if (last) {
      return (data.title || data.id || "가동") + "  ·  " +
        (last.accepted ? "수락" : "거절") +
        (last.reason ? "  ·  " + ko(KO.alarm, last.reason) : "") +
        (last.lot_status ? "  ·  " + koStatus(last.lot_status) : "");
    }
    return data.ok ? "됨" : "실패";
  }

  async function loadScenarios() {
    const rows = await getJson("/api/lab/scenarios");
    scenarioButtons.innerHTML = "";
    demoButtons.innerHTML = "";
    for (const row of rows) {
      const el = document.createElement("button");
      el.type = "button";
      const short = {
        demo_oled_pass: "올레드 1장 투입",
        demo_oled_fail: "검사 불량",
        demo_lcd_pass: "엘시디 1장",
        demo_comm_loss: "줄 끊기",
        demo_alive: "다시 살리기",
        demo_recipe_mismatch: "조건 틀림",
      };
      el.textContent = short[row.id] || row.title;
      el.title = row.what;
      el.addEventListener("click", async function () {
        const hint = document.getElementById("scenarioHint");
        const product = row.id.indexOf("lcd") >= 0 ? "LCD" : "OLED";
        el.disabled = true;
        if (hint) hint.textContent = koProduct(product) + " 유리를 라인에 올리는 중";
        const skipWalk = row.id === "demo_comm_loss" || row.id === "demo_alive";
        const walk = skipWalk ? Promise.resolve() : playRoute(product, "시연");
        try {
          const res = await fetch("/api/lab/scenarios/" + row.id + "/run", { method: "POST" });
          const data = await res.json();
          await walk;
          const msg = shortScenario(data);
        if (hint) {
          if (row.id === "demo_comm_loss") hint.textContent = "증착 1호기 줄이 끊겼습니다. 실적이 거절됩니다.";
          else if (row.id === "demo_alive") hint.textContent = "라인 설비를 다시 살렸습니다.";
          else hint.textContent = msg;
        }
          scenarioOut.textContent = msg + "\n\n" + JSON.stringify(data, null, 2);
        } catch (err) {
          await walk;
          if (hint) hint.textContent = "명령을 못 보냈습니다. " + err;
        }
        el.disabled = false;
        refresh();
      });
      if (String(row.id).indexOf("demo_") === 0) {
        demoButtons.appendChild(el);
        demoButtons.appendChild(document.createTextNode(" "));
      } else {
        scenarioButtons.appendChild(el);
        scenarioButtons.appendChild(document.createTextNode(" "));
      }
    }
  }

  async function refresh() {
    if (refreshing || playing) return;
    refreshing = true;
    let eq, lots, kpi, lineInfo, events, orders, wip, production, alarms, commands, interfaces;
    try {
    [eq, lots, kpi, lineInfo, events, orders, wip, production, alarms, commands, interfaces] = await Promise.all([
      getJson("/api/equipment"),
      getJson("/api/lots"),
      getJson("/api/kpis"),
      getJson("/api/line"),
      getJson("/api/events/recent"),
      getJson("/api/work-orders"),
      getJson("/api/wip"),
      getJson("/api/production"),
      getJson("/api/alarms?unresolved_only=true"),
      getJson("/api/commands"),
      getJson("/api/equipment/interfaces"),
    ]);
    const oledPath = (lineInfo.oled_route || []).map(koStep).join(" → ");
    const lcdPath = (lineInfo.lcd_route || []).map(koStep).join(" → ");
    routes.textContent = "OLED  " + oledPath + "    ·    LCD  " + lcdPath + "    ·    " + (lineInfo.note || "");
    if (kpis) kpis.innerHTML = "";
    if (toolYield) toolYield.textContent = "";
    if (productionBox) productionBox.textContent = "";
    const blocked = [];
    if (production.hold_lots && production.hold_lots.length) blocked.push("멈춤 " + production.hold_lots.length + "건");
    if (production.offline_equipment && production.offline_equipment.length) blocked.push("줄 끊김 " + production.offline_equipment.length + "대");
    if (blockedBox) blockedBox.textContent = blocked.join(" · ");
    closeoutBox.innerHTML = "";
    const close = production.closeout || {};
    const addClose = function (label, value, cls) {
      const box = document.createElement("div");
      box.className = "kpi";
      const lab = document.createElement("span");
      lab.textContent = label;
      const num = document.createElement("b");
      num.textContent = value == null ? "-" : String(value);
      if (cls) num.className = cls;
      box.appendChild(lab);
      box.appendChild(num);
      closeoutBox.appendChild(box);
    };
    addClose("끝낸", close.complete, close.complete ? "COMPLETE" : "");
    addClose("남은", close.remaining);
    addClose("멈춤", close.hold_lots, close.hold_lots ? "HOLD" : "");
    addClose("끊김", close.offline, close.offline ? "OFFLINE" : "");

    wipBox.innerHTML = "";
    ["LOAD", "CLEAN", "EVAP", "ENCAP", "PI", "LCD_CELL", "INSPECT"].forEach(function (key) {
      const box = document.createElement("div");
      box.className = "wip-step";
      const lab = document.createElement("span");
      lab.textContent = koStep(key);
      const num = document.createElement("b");
      num.textContent = String((wip.by_step && wip.by_step[key]) || 0);
      box.appendChild(lab);
      box.appendChild(num);
      wipBox.appendChild(box);
    });
    ["COMPLETE", "FAIL", "SCRAP"].forEach(function (key) {
      const box = document.createElement("div");
      box.className = "wip-step";
      const lab = document.createElement("span");
      lab.textContent = koStep(key);
      const num = document.createElement("b");
      num.textContent = String(wip[key.toLowerCase()] || 0);
      if (key !== "COMPLETE") num.className = key;
      box.appendChild(lab);
      box.appendChild(num);
      wipBox.appendChild(box);
    });

    const byId = {};
    eq.forEach(function (row) { byId[row.id] = row; });
    const ifaceById = {};
    (interfaces || []).forEach(function (row) { ifaceById[row.equipment_id] = row; });
    document.querySelectorAll(".chamber[data-eq]").forEach(function (el) {
      const row = byId[el.getAttribute("data-eq")];
      const st = chamberState(row);
      el.className = "chamber " + (row ? row.connection_status : "") + " " + st.cls;
      el.innerHTML = "";
      const id = document.createElement("div");
      id.className = "eq-id";
      id.textContent = row ? koEq(row.id) : "";
      const title = document.createElement("h3");
      title.textContent = row ? (KO.eqName[row.id] || koStep(row.process_step)) : "-";
      const bits = [st.text, row && row.current_lot_id ? "카세트" : "빔"];
      if (row && row.current_recipe_id) bits.push(koRecipe(row.current_recipe_id));
      const state = line(bits.join(" · "), st.cls);
      state.className = "state " + st.cls;
      const tokens = document.createElement("div");
      tokens.className = "tokens";
      tokensOnEquipment(el.getAttribute("data-eq"), row, wip.cassettes).forEach(function (cst) {
        tokens.appendChild(makeToken(cst));
      });
      el.appendChild(id);
      el.appendChild(title);
      el.appendChild(state);
      el.appendChild(tokens);
      if (!row) return;
      const iface = ifaceById[row.id];
      if (iface) {
        const signal = document.createElement("div");
        signal.className = "signal";
        const bits = [koInterface(iface.interface_type) + " " + (iface.transport || "")];
        if (iface.chamber_temperature != null) {
          bits.push(iface.chamber_temperature + "℃ / " + iface.vacuum_pressure);
        } else {
          bits.push("측정값 없음");
        }
        if (iface.downtime_sec_today > 0) {
          bits.push("정지 " + Math.round(iface.downtime_sec_today) + "초");
        }
        if (iface.open_downtime_reason) {
          bits.push(ko(KO.alarm, iface.open_downtime_reason) + " 진행 중");
        }
        signal.textContent = bits.join("  ·  ");
        el.appendChild(signal);
      }
      const btns = document.createElement("div");
      btns.className = "btns";
      const start = document.createElement("button");
      start.type = "button";
      start.textContent = "켜기";
      start.setAttribute("data-cmd", "START");
      start.setAttribute("data-eq", row.id);
      const stop = document.createElement("button");
      stop.type = "button";
      stop.textContent = "끄기";
      stop.setAttribute("data-cmd", "STOP");
      stop.setAttribute("data-eq", row.id);
      const recipe = document.createElement("button");
      recipe.type = "button";
      recipe.textContent = "조건";
      recipe.setAttribute("data-cmd", "SELECT_RECIPE");
      recipe.setAttribute("data-eq", row.id);
      recipe.setAttribute("data-recipe", row.product_scope === "LCD" ? "RCP-LCD-C01" : "RCP-OLED-A01");
      btns.appendChild(start);
      btns.appendChild(stop);
      btns.appendChild(recipe);
      if (row.current_lot_id) {
        const hold = document.createElement("button");
        hold.type = "button";
        hold.textContent = "멈추기";
        hold.setAttribute("data-cmd", "HOLD_LOT");
        hold.setAttribute("data-lot", row.current_lot_id);
        btns.appendChild(hold);
      }
      el.appendChild(btns);
    });
    const waitBox = document.getElementById("waitTokens");
    if (waitBox) {
      waitBox.innerHTML = "";
      waitingCassettes(wip.cassettes, eq).forEach(function (cst) {
        waitBox.appendChild(makeToken(cst));
      });
    }
    const doneBox = document.getElementById("doneTokens");
    if (doneBox) {
      doneBox.innerHTML = "";
      finishedCassettes(wip.cassettes).forEach(function (cst) {
        doneBox.appendChild(makeToken(cst));
      });
    }

    const holds = lots.filter(function (row) { return row.status === "HOLD"; });
    holdCards.innerHTML = "";
    if (!holds.length) {
      holdCards.appendChild(line("보류된 작업 없음", "hint"));
    }
    for (const row of holds) {
      const card = document.createElement("div");
      card.className = "hold-card";
      const title = document.createElement("h3");
      title.textContent = row.id;
      card.appendChild(title);
      card.appendChild(line(ko(KO.alarm, row.hold_reason), "HOLD"));
      const holdBtns = document.createElement("div");
      holdBtns.className = "btns";
      holdBtns.appendChild(makeBtn("왜", function () { showDiag(row.id); }));
      holdBtns.appendChild(makeBtn("다시", function () {
        sendCommand({ command_type: "RELEASE_LOT", lot_id: row.id });
      }));
      holdBtns.appendChild(makeBtn("버리기", async function () {
        const slots = await getJson("/api/lots/" + encodeURIComponent(row.id) + "/slots");
        const fails = (slots.slots || []).filter(function (s) { return s.status === "FAIL"; });
        for (const glass of fails) {
          await sendCommand({ command_type: "SCRAP_PANEL", panel_id: glass.panel_id });
        }
      }));
      card.appendChild(holdBtns);
      holdCards.appendChild(card);
    }
    const holdKey = holds.map(function (row) { return row.id; }).join(",");
    if (holdKey !== lastHoldKey) {
      lastHoldKey = holdKey;
      if (holds[0]) showDiag(holds[0].id);
      else diagOut.textContent = "";
    }

    alarmCards.innerHTML = "";
    if (!alarms.length) {
      alarmCards.appendChild(line("확인 안 한 알람 없음", "hint"));
    }
    for (const row of alarms.slice(0, 8)) {
      const card = document.createElement("div");
      card.className = "alarm-card";
      const title = document.createElement("h3");
      title.textContent = ko(KO.alarm, row.alarm_code);
      card.appendChild(title);
      card.appendChild(line(alarmSay(row)));
      card.appendChild(makeBtn("확인함", function () {
        sendCommand({ command_type: "ACK_ALARM", alarm_id: row.alarm_id, equipment_id: row.equipment_id, lot_id: row.lot_id });
      }));
      alarmCards.appendChild(card);
    }
    woRows.innerHTML = "";
    for (const row of orders) {
      const tr = document.createElement("tr");
      tr.appendChild(cell(row.id));
      tr.appendChild(cell(koProduct(row.product_type)));
      tr.appendChild(cell((row.complete || 0) + "/" + row.qty));
      tr.appendChild(cell(koStatus(row.status), row.status));
      woRows.appendChild(tr);
    }
    lotBody.innerHTML = "";
    for (const row of lots) {
      const tr = document.createElement("tr");
      tr.appendChild(cell(row.id));
      tr.appendChild(cell(koStatus(row.status), row.status));
      const loc = wip.cassettes.find(function (c) { return c.lot_id === row.id; });
      tr.appendChild(cell(loc && loc.next_step ? koStep(loc.next_step) : "-"));
      lotBody.appendChild(tr);
    }
    feed.innerHTML = "";
    for (const row of events.slice(0, 25)) {
      const li = document.createElement("li");
      li.textContent = [
        ko(KO.event, row.event_type),
        koEq(row.equipment_id) || "-",
        row.lot_id ? "작업 " + row.lot_id : "",
        row.panel_id ? "유리 " + row.panel_id : "",
        row.process_step ? koStep(row.process_step) : "",
        row.accepted ? "수락" : "거절",
        row.reason ? ko(KO.alarm, row.reason) : "",
      ].filter(Boolean).join("  ·  ");
      feed.appendChild(li);
    }
    cmdFeed.innerHTML = "";
    if (!commands.length) {
      const empty = document.createElement("li");
      empty.textContent = "보낸 명령 없음";
      empty.className = "hint";
      cmdFeed.appendChild(empty);
    }
    for (const row of commands.slice(0, 12)) {
      const li = document.createElement("li");
      li.textContent = [
        ko(KO.cmd, row.command_type),
        ko(KO.cmdStatus, row.status),
        koEq(row.equipment_id) || row.lot_id || row.panel_id || "",
        koText(row.message || ""),
      ].filter(Boolean).join("  ·  ");
      cmdFeed.appendChild(li);
    }
    } catch (err) {
      const hint = document.getElementById("scenarioHint");
      if (hint) hint.textContent = "화면을 못 읽었습니다. " + err;
    }
    refreshing = false;
  }

  const fab = document.querySelector(".fab");
  if (fab) {
    fab.addEventListener("click", function (ev) {
      const btn = ev.target.closest("button[data-cmd]");
      if (!btn) return;
      ev.preventDefault();
      sendCommand({
        command_type: btn.getAttribute("data-cmd"),
        equipment_id: btn.getAttribute("data-eq") || null,
        lot_id: btn.getAttribute("data-lot") || null,
        recipe_id: btn.getAttribute("data-recipe") || null,
      });
    });
  }

  document.getElementById("woForm").addEventListener("submit", async function (ev) {
    ev.preventDefault();
    const res = await fetch("/api/work-orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_type: document.getElementById("woProduct").value,
        recipe_id: document.getElementById("woRecipe").value,
        qty: Number(document.getElementById("woQty").value),
      }),
    });
    const data = await res.json();
    woOut.textContent = data.id
      ? "투입 됨  ·  지시 " + data.id + "  ·  작업묶음 " + data.lot_id + "  ·  카세트 " + data.cassette_id
      : JSON.stringify(data, null, 2);
    if (data.id) lastWoId = data.id;
    if (data.lot_id) {
      document.getElementById("cmdLot").value = data.lot_id;
    }
    refresh();
  });

  document.getElementById("woRun").addEventListener("click", async function () {
    let id = lastWoId;
    if (!id) {
      const rows = await getJson("/api/work-orders");
      id = rows.length ? rows[0].id : "";
    }
    if (!id) {
      woOut.textContent = "먼저 투입하세요.";
      return;
    }
    const orders = await getJson("/api/work-orders");
    const order = orders.find(function (row) { return row.id === id; }) || orders[0];
    const product = order && order.product_type === "LCD" ? "LCD" : "OLED";
    const hint = document.getElementById("scenarioHint");
    if (hint) hint.textContent = koProduct(product) + " 유리가 라인을 도는 중";
    const walk = playRoute(product, "시연");
    const res = await fetch("/api/lab/run-order/" + encodeURIComponent(id), { method: "POST" });
    const data = await res.json();
    await walk;
    const errText = data.error ? koText(String(data.error)) : "거절";
    woOut.textContent = data.ok
      ? "가동 끝  ·  지시 " + (data.work_order_id || id) + "  ·  작업묶음 " + (data.lot_id || "-")
      : "가동 멈춤  ·  " + errText;
    if (hint) {
      hint.textContent = data.ok
        ? koProduct(product) + " 한 장이 라인을 통과했습니다."
        : "라인이 멈췄습니다. " + errText;
    }
    refresh();
  });

  document.getElementById("woProduct").addEventListener("change", function () {
    const recipe = document.getElementById("woRecipe");
    recipe.value = this.value === "LCD" ? "RCP-LCD-C01" : "RCP-OLED-A01";
  });

  document.getElementById("cmdForm").addEventListener("submit", async function (ev) {
    ev.preventDefault();
    const body = {
      command_type: document.getElementById("cmdType").value,
      lot_id: document.getElementById("cmdLot").value || null,
      equipment_id: document.getElementById("cmdEq").value || null,
      alarm_id: document.getElementById("cmdAlarm").value || null,
      panel_id: document.getElementById("cmdPanel").value || null,
      recipe_id: document.getElementById("cmdRecipe").value || null,
    };
    const res = await fetch("/api/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    try {
      const data = JSON.parse(text);
      document.getElementById("cmdResult").textContent =
        ko(KO.cmd, data.command_type) + "  ·  " + ko(KO.cmdStatus, data.status) + "  ·  " + koText(data.message || "");
    } catch (err) {
      document.getElementById("cmdResult").textContent = text;
    }
    refresh();
  });

  let lastExportEvents = [];
  const replayOut = document.getElementById("replayOut");

  async function exportSource() {
    const src = document.getElementById("replaySrc").value.trim();
    const data = await getJson("/api/lab/export/" + encodeURIComponent(src));
    lastExportEvents = data.events || [];
    replayOut.textContent = "꺼낸 이력 " + (data.count || lastExportEvents.length) + "건  ·  유리 " + src;
    return data;
  }

  document.getElementById("replayExport").addEventListener("click", async function () {
    try {
      await exportSource();
    } catch (err) {
      replayOut.textContent = String(err);
    }
  });

  document.getElementById("replayForm").addEventListener("submit", async function (ev) {
    ev.preventDefault();
    try {
      if (!lastExportEvents.length) {
        await exportSource();
      }
      const res = await fetch("/api/lab/replay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          events: lastExportEvents,
          refresh_timestamps: true,
          lot_id: document.getElementById("replayLot").value.trim() || null,
          panel_id: document.getElementById("replayDst").value.trim() || null,
        }),
      });
      const data = await res.json();
      replayOut.textContent = data.ok ? "다시 넣음" : ("거절  ·  " + (data.error || data.detail || ""));
      refresh();
    } catch (err) {
      replayOut.textContent = String(err);
    }
  });

  refresh();
  loadScenarios().catch(function (err) {
    const hint = document.getElementById("scenarioHint");
    if (hint) hint.textContent = "운전 버튼을 못 불러왔습니다. " + err;
  });
  setInterval(refresh, 2500);
  setInterval(async function() {
    if (playing) return;
    try {
      await fetch("/api/lab/scenarios/heartbeat/run", { method: "POST" });
    } catch(e) {}
  }, 10000);
}

function mesDotClass(state) {
  if (state === "done") return "dot done";
  if (state === "now") return "dot now";
  if (state === "hold") return "dot hold";
  return "dot wait";
}

function startMesBoard() {
  const noteEl = document.getElementById("note");
  const kpiEl = document.getElementById("kpis");
  const orderEl = document.getElementById("orders");
  const lotEl = document.getElementById("lots");
  const eqEl = document.getElementById("eq");
  const holdEl = document.getElementById("holds");
  const lineEl = document.getElementById("mesLine");

  async function refresh() {
    const board = await getJson("/api/mes/board");
    noteEl.textContent = board.note;
    const prod = board.production || {};
    const close = prod.closeout || {};
    kpiEl.innerHTML = "";
    [
      ["올레드 완료", ((prod.oled && prod.oled.complete) || 0) + " / " + ((prod.oled && prod.oled.target) || 0)],
      ["엘시디 완료", ((prod.lcd && prod.lcd.complete) || 0) + " / " + ((prod.lcd && prod.lcd.target) || 0)],
      ["오늘 끝낸 장", close.complete || 0],
      ["멈춘 작업", (board.holds || []).length],
      ["줄 끊긴 기계", board.equipment_offline || 0],
    ].forEach(function (pair) {
      const box = document.createElement("div");
      box.className = "kpi";
      box.innerHTML = "<span>" + pair[0] + "</span><b>" + pair[1] + "</b>";
      kpiEl.appendChild(box);
    });

    orderEl.innerHTML = "";
    (board.orders || []).forEach(function (row) {
      const tr = document.createElement("tr");
      tr.appendChild(cell(row.id));
      tr.appendChild(cell(koProduct(row.product_type)));
      tr.appendChild(cell(row.complete + " / " + row.qty));
      tr.appendChild(cell(koStatus(row.status), row.status));
      orderEl.appendChild(tr);
    });
    if (!board.orders || !board.orders.length) {
      const tr = document.createElement("tr");
      tr.appendChild(cell("오늘 지시가 없습니다. 운전에서 올레드 1장 투입을 누르세요."));
      tr.firstChild.colSpan = 4;
      orderEl.appendChild(tr);
    }

    lotEl.innerHTML = "";
    (board.lots || []).forEach(function (lot) {
      const card = document.createElement("article");
      card.className = "mes-lot" + (lot.status === "HOLD" ? " HOLD" : "");
      const title = document.createElement("h3");
      title.textContent = lot.lot_id + "  ·  " + koProduct(lot.product_type) + "  ·  " + koStatus(lot.status);
      const sub = document.createElement("p");
      const where = lot.current_step
        ? "지금 " + koStep(lot.current_step) + (lot.current_equipment_id ? " · " + (KO.eqName[lot.current_equipment_id] || lot.current_equipment_id) : "")
        : (lot.next_step ? "다음 " + koStep(lot.next_step) : "끝");
      sub.textContent = lot.cassette_id + "  ·  " + where + "  ·  " + koRecipe(lot.recipe_id);
      const route = document.createElement("ol");
      route.className = "route";
      (lot.route || []).forEach(function (step) {
        const li = document.createElement("li");
        li.className = mesDotClass(step.state);
        li.innerHTML = "<b>" + koStep(step.step) + "</b><span>" + step.done + "/" + step.total + "</span>";
        route.appendChild(li);
      });
      card.appendChild(title);
      card.appendChild(sub);
      card.appendChild(route);
      lotEl.appendChild(card);
    });

    eqEl.innerHTML = "";
    (board.equipment || []).forEach(function (row) {
      const tr = document.createElement("tr");
      tr.appendChild(cell(KO.eqName[row.id] || row.id));
      tr.appendChild(cell(koStatus(row.equipment_status), row.equipment_status));
      tr.appendChild(cell(ko(KO.conn, row.connection_status), row.connection_status));
      tr.appendChild(cell(row.current_lot_id || "비어 있음"));
      eqEl.appendChild(tr);
    });

    if (lineEl) {
      lineEl.innerHTML = "";
      (board.equipment || []).forEach(function (row) {
        const st = chamberState(row);
        const mini = document.createElement("div");
        mini.className = "mini-chamber " + st.cls;
        const here = (board.lots || []).filter(function (lot) {
          return lot.current_equipment_id === row.id;
        });
        mini.innerHTML = "<h3>" + (KO.eqName[row.id] || row.id) + "</h3><span class=\"" + st.cls + "\">" + st.text + "</span>";
        const tokens = document.createElement("div");
        tokens.className = "tokens";
        here.forEach(function (lot) {
          tokens.appendChild(makeToken({
            lot_id: lot.lot_id,
            cassette_id: lot.cassette_id,
            product_type: lot.product_type,
            status: lot.status,
          }));
        });
        mini.appendChild(tokens);
        lineEl.appendChild(mini);
      });
    }

    holdEl.innerHTML = "";
    if (!board.holds || !board.holds.length) {
      holdEl.innerHTML = "<p class=\"hint\">지금 멈춘 작업이 없습니다.</p>";
    }
    (board.holds || []).forEach(function (lot) {
      const card = document.createElement("article");
      card.className = "hold-card";
      const why = lot.hold_reason === "INSPECT_FAIL"
        ? "검사에서 불량이 나와 멈췄습니다."
        : (lot.hold_reason ? "이유: " + ko(KO.alarm, lot.hold_reason) : "보류입니다.");
      card.innerHTML = "<h3>" + lot.lot_id + "</h3><p>" + why + "</p><p>합격 " + lot.complete + " · 불량 " + lot.fail + " · 폐기 " + lot.scrap + "</p>";
      holdEl.appendChild(card);
    });

    await refreshOee();
  }

  refresh();
  setInterval(refresh, 3000);
}

function pct(value) {
  if (value == null) return "-";
  return Math.round(value * 1000) / 10 + "%";
}

async function refreshOee() {
  const kpiEl = document.getElementById("oeeKpis");
  const rowsEl = document.getElementById("oeeRows");
  const noteEl = document.getElementById("oeeNote");
  if (!kpiEl || !rowsEl) return;
  const data = await getJson("/api/analytics/oee");

  kpiEl.innerHTML = "";
  [
    ["가동률", pct(data.availability)],
    ["성능", pct(data.performance)],
    ["품질", pct(data.quality)],
    ["OEE", pct(data.oee)],
  ].forEach(function (pair) {
    const box = document.createElement("div");
    box.className = "kpi";
    box.innerHTML = "<span>" + pair[0] + "</span><b>" + pair[1] + "</b>";
    kpiEl.appendChild(box);
  });

  if (noteEl) {
    const bits = ["계획시간 " + data.planned_basis, "합격 " + data.good, "불량 " + data.bad];
    if (data.missing && data.missing.length) bits.push(data.missing.join(" · "));
    noteEl.textContent = bits.join("  ·  ");
  }

  rowsEl.innerHTML = "";
  (data.equipment || []).forEach(function (row) {
    const tr = document.createElement("tr");
    tr.appendChild(cell(KO.eqName[row.equipment_id] || row.equipment_id));
    tr.appendChild(cell(row.processed));
    tr.appendChild(cell(Math.round(row.downtime_sec), row.downtime_sec > 0 ? "OFFLINE" : ""));
    tr.appendChild(cell(pct(row.availability)));
    tr.appendChild(cell(pct(row.performance)));
    tr.appendChild(cell(pct(row.quality)));
    tr.appendChild(cell(pct(row.oee)));
    rowsEl.appendChild(tr);
  });
}
