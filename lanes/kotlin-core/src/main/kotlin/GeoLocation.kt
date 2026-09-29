import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * A WGS-84 geographic coordinate pair (latitude/longitude in decimal degrees).
 *
 * Used internally for radius-based discovery filtering (AC#3). Location data
 * is never shown to other users — only a town/city label is exposed, per
 * docs/product-decisions.md decision 3: "town/city only — never a distance,
 * never coordinates." It is read only while the person is actively using the
 * app (AC#12 / constitution P4, enforceable).
 *
 * The same shape exists verbatim in the Swift lane (GeoLocation.swift) so
 * that both platforms share one model of a geographic location (constitution
 * P9).
 */
data class GeoLocation(
    val lat: Double,
    val lon: Double,
) {
    /**
     * Returns the great-circle distance in kilometres between this location
     * and [other] using the haversine formula.
     *
     * Accuracy is within ~0.3 % over the 1–25 km distances this app uses,
     * which is sufficient for the radius values in [SearchRadius].
     */
    fun distanceTo(other: GeoLocation): Double {
        val lat1 = Math.toRadians(lat)
        val lat2 = Math.toRadians(other.lat)
        val dLat = Math.toRadians(other.lat - lat)
        val dLon = Math.toRadians(other.lon - lon)
        val sinHalfDLat = sin(dLat / 2)
        val sinHalfDLon = sin(dLon / 2)
        val a =
            sinHalfDLat * sinHalfDLat +
                cos(lat1) * cos(lat2) * sinHalfDLon * sinHalfDLon
        val c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return EARTH_RADIUS_KM * c
    }

    companion object {
        /** Mean Earth radius in kilometres (WGS-84). */
        private const val EARTH_RADIUS_KM = 6371.0
    }
}

/**
 * The four discovery-radius values a person can choose (AC#3).
 *
 * The allowed values are exactly 1, 5, 10 and 25 kilometres, as stated in
 * the acceptance criterion.
 *
 * The same values exist verbatim in the Swift lane (GeoLocation.swift) so
 * that both platforms enforce one shared set of choices (constitution P9).
 */
enum class SearchRadius(
    val kilometres: Double,
) {
    ONE(1.0),
    FIVE(5.0),
    TEN(10.0),
    TWENTY_FIVE(25.0),
}
