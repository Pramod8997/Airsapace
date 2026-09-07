/** Stylized India airport positions on a 1000×1150 viewBox (approx lon/lat → linear map). */
export interface AirportXY { iata: string; x: number; y: number }

// Approx coordinates, eyeballed for a legible schematic (not survey-grade — UI_UX_DESIGN.md §9 "stylized").
const RAW: Array<[string, number, number]> = [
  // [iata, lon, lat]
  ['DEL', 77.1, 28.6],
  ['BOM', 72.9, 19.1],
  ['BLR', 77.6, 13.2],
  ['HYD', 78.4, 17.5],
  ['MAA', 80.2, 13.1],
  ['CCU', 88.4, 22.6],
]

// Map bounds used for projection
const LON_MIN = 68, LON_MAX = 90, LAT_MIN = 8, LAT_MAX = 34

export const AIRPORTS: Record<string, AirportXY> = Object.fromEntries(
  RAW.map(([iata, lon, lat]) => {
    const x = ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * 900 + 50
    const y = ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * 1000 + 70
    return [iata, { iata, x, y }]
  }),
)
