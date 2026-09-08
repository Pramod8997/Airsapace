/** India airport coordinates and metadata for interactive maps (Leaflet) and route observatory. */
export interface Airport {
  iata: string
  name: string
  city: string
  lat: number
  lng: number
  x: number
  y: number
}

// Exact WGS84 latitude and longitude coordinates for major Indian airports
const RAW: Array<[string, string, string, number, number]> = [
  // [iata, name, city, lat, lon]
  ['DEL', 'Indira Gandhi International Airport', 'New Delhi', 28.5562, 77.1000],
  ['BOM', 'Chhatrapati Shivaji Maharaj International Airport', 'Mumbai', 19.0896, 72.8656],
  ['BLR', 'Kempegowda International Airport', 'Bengaluru', 13.1986, 77.7066],
  ['HYD', 'Rajiv Gandhi International Airport', 'Hyderabad', 17.2403, 78.4294],
  ['MAA', 'Chennai International Airport', 'Chennai', 12.9941, 80.1709],
  ['CCU', 'Netaji Subhash Chandra Bose International Airport', 'Kolkata', 22.6547, 88.4467],
]

// Map bounds used for backward compatibility SVG projection
const LON_MIN = 68, LON_MAX = 90, LAT_MIN = 8, LAT_MAX = 34

export const AIRPORTS: Record<string, Airport> = Object.fromEntries(
  RAW.map(([iata, name, city, lat, lon]) => {
    const x = ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * 900 + 50
    const y = ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * 1000 + 70
    return [iata, { iata, name, city, lat, lng: lon, x, y }]
  }),
)
