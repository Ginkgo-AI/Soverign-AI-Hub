/**
 * Chart data detection and analysis utilities.
 * No recharts dependency — safe for SSR.
 */

export interface DataPoint {
  [key: string]: string | number;
}

export interface ChartConfig {
  type: "bar" | "line" | "pie" | "area" | "table";
  title?: string;
  data: DataPoint[];
  xKey?: string;
  yKeys?: string[];
  nameKey?: string;
  valueKey?: string;
}

export function tryFixJson(text: string): string {
  let fixed = text.trim();
  fixed = fixed.split("\n").map((l) => l.trim()).join("");
  fixed = fixed.replace(/,(\s*[}\]])/g, "$1");
  fixed = fixed.replace(/'/g, '"');
  fixed = fixed.replace(/\/\/.*/g, "");
  fixed = fixed.replace(/([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:/g, '$1"$2":');
  if (fixed.startsWith("{") && fixed.includes("},{")) fixed = "[" + fixed;
  if (fixed.startsWith("[") && !fixed.endsWith("]") && fixed.endsWith("}")) fixed += "]";
  if (!fixed.startsWith("[") && fixed.endsWith("]") && fixed.startsWith("{")) fixed = "[" + fixed;
  return fixed;
}

export function analyzeData(data: unknown, suggestedType?: string): ChartConfig | null {
  if (!data) return null;

  let parsed = data;
  if (typeof data === "string") {
    try {
      parsed = JSON.parse(tryFixJson(data));
    } catch {
      return null;
    }
  }

  if (!Array.isArray(parsed) || parsed.length === 0) {
    if (typeof parsed === "object" && parsed !== null) {
      const obj = parsed as Record<string, unknown>;
      if (obj.type && obj.data && Array.isArray(obj.data)) {
        return {
          type: obj.type as ChartConfig["type"],
          title: obj.title as string | undefined,
          data: obj.data as DataPoint[],
          xKey: obj.xKey as string | undefined,
          yKeys: obj.yKeys as string[] | undefined,
          nameKey: obj.nameKey as string | undefined,
          valueKey: obj.valueKey as string | undefined,
        };
      }
      // Handle columnar format: {dates: [...], AAPL: [...], GOOG: [...]}
      const entries = Object.entries(obj);
      const arrayEntries = entries.filter(([, v]) => Array.isArray(v) && (v as unknown[]).length > 0);
      if (arrayEntries.length >= 2) {
        // Find the label/date column (string arrays) and value columns (number arrays)
        const labelEntry = arrayEntries.find(([k, v]) =>
          /date|time|label|name|x/i.test(k) && typeof (v as unknown[])[0] === "string"
        ) || arrayEntries.find(([, v]) => typeof (v as unknown[])[0] === "string");
        const numEntries = arrayEntries.filter(([, v]) => typeof (v as unknown[])[0] === "number");

        if (numEntries.length > 0) {
          const len = (numEntries[0][1] as number[]).length;
          const rows: DataPoint[] = [];
          for (let i = 0; i < len; i++) {
            const row: DataPoint = {};
            if (labelEntry) {
              row[labelEntry[0]] = (labelEntry[1] as string[])[i];
            } else {
              row["index"] = i;
            }
            for (const [k, v] of numEntries) {
              row[k] = Math.round(((v as number[])[i] + Number.EPSILON) * 100) / 100;
            }
            rows.push(row);
          }
          const xKey = labelEntry ? labelEntry[0] : "index";
          return {
            type: rows.length > 10 ? "line" : "bar",
            data: rows,
            xKey,
            yKeys: numEntries.map(([k]) => k),
          };
        }
      }

      // Handle simple key-value object: {A: 10, B: 20}
      if (entries.every(([, v]) => typeof v === "number")) {
        return {
          type: (suggestedType as ChartConfig["type"]) || "pie",
          data: entries.map(([name, value]) => ({ name, value: value as number })),
          nameKey: "name",
          valueKey: "value",
        };
      }
    }
    return null;
  }

  const dataArray = parsed as DataPoint[];
  const firstItem = dataArray[0];
  if (typeof firstItem !== "object" || firstItem === null) return null;

  const keys = Object.keys(firstItem);
  const stringKeys = keys.filter((k) => typeof firstItem[k] === "string");
  const numberKeys = keys.filter((k) => typeof firstItem[k] === "number");

  if (numberKeys.length === 0) {
    return { type: "table", data: dataArray };
  }

  let chartType: ChartConfig["type"] = (suggestedType as ChartConfig["type"]) || "bar";
  if (!suggestedType) {
    if (numberKeys.length === 1 && stringKeys.length === 1 && dataArray.length <= 8) {
      chartType = "pie";
    } else if (dataArray.length > 10 && numberKeys.length <= 3) {
      chartType = "line";
    } else if (numberKeys.length > 3) {
      chartType = "area";
    }
  }

  const xKey =
    stringKeys[0] ||
    keys.find((k) => /name|label|date|time|category/i.test(k)) ||
    keys[0];

  return {
    type: chartType,
    data: dataArray,
    xKey,
    yKeys: numberKeys,
    nameKey: stringKeys[0] || "name",
    valueKey: numberKeys[0] || "value",
  };
}

export function isChartData(text: string): boolean {
  if (!text) return false;
  let trimmed = text.trim();
  if (!trimmed.startsWith("[") && !trimmed.startsWith("{")) return false;
  trimmed = tryFixJson(trimmed);
  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed) && parsed.length > 0) {
      const first = parsed[0];
      if (typeof first === "object" && first !== null) {
        return Object.values(first).some((v) => typeof v === "number");
      }
    }
    if (typeof parsed === "object" && parsed !== null) {
      const obj = parsed as Record<string, unknown>;
      if (obj.type && obj.data) return true;
      const values = Object.values(obj);
      return values.length > 0 && values.every((v) => typeof v === "number");
    }
    return false;
  } catch {
    return false;
  }
}
