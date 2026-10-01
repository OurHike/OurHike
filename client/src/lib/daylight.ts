// Whether the sun is up at a place and time (#1056) - so the forecast's hour
// boxes can draw a sun by day and a moon by night.
//
// The Astronomical Almanac's low-precision solar coordinates (the "Sun"
// entry of its Section C, which it gives as good to 0.01° between 1950 and
// 2050), and the standard definition of sunrise: the sun's centre 0.833° below
// the horizon, which is refraction plus the sun's own radius. Nothing else in
// the app needs the sun yet; this is the smallest thing that answers "day or
// night" and it is not an ephemeris.
//
// Checked against `astral` 3.2, an independent implementation of NOAA's solar
// calculator, at four trail points on four dates (daylight.test.ts): within a
// minute of its sunrise and sunset at every one.

const DEG = Math.PI / 180

/** The sun's height above the horizon in degrees, at `lat`/`lon` (degrees,
 *  east positive) and instant `time`. */
export function solarElevation(lat: number, lon: number, time: Date): number {
  const n = time.getTime() / 86_400_000 + 2440587.5 - 2451545.0
  const meanLongitude = (280.46 + 0.9856474 * n) % 360
  const meanAnomaly = ((357.528 + 0.9856003 * n) % 360) * DEG
  const eclipticLongitude =
    (meanLongitude + 1.915 * Math.sin(meanAnomaly) + 0.02 * Math.sin(2 * meanAnomaly)) *
    DEG
  const obliquity = (23.439 - 0.0000004 * n) * DEG

  const rightAscension = Math.atan2(
    Math.cos(obliquity) * Math.sin(eclipticLongitude),
    Math.cos(eclipticLongitude),
  )
  const declination = Math.asin(Math.sin(obliquity) * Math.sin(eclipticLongitude))
  const siderealDegrees = ((18.697374558 + 24.06570982441908 * n) % 24) * 15
  const hourAngle = (siderealDegrees + lon) * DEG - rightAscension

  return (
    Math.asin(
      Math.sin(lat * DEG) * Math.sin(declination) +
        Math.cos(lat * DEG) * Math.cos(declination) * Math.cos(hourAngle),
    ) / DEG
  )
}

/** The sun's centre is higher than 0.833° below the horizon. */
export function isDaylight(lat: number, lon: number, time: Date): boolean {
  return solarElevation(lat, lon, time) > -0.833
}
