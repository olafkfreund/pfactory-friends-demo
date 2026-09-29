import Foundation

/// A WGS-84 geographic coordinate pair (latitude/longitude in decimal degrees).
///
/// Used internally for radius-based discovery filtering (AC#3). Location data
/// is never shown to other users — only a town/city label is exposed, per
/// `docs/product-decisions.md` decision 3: "town/city only — never a distance,
/// never coordinates." It is read only while the person is actively using the
/// app (AC#12 / constitution P4, enforceable).
///
/// The same shape exists verbatim in the Kotlin lane (GeoLocation.kt) so that
/// both platforms share one model of a geographic location (constitution P9).
public struct GeoLocation: Equatable {
    public let lat: Double
    public let lon: Double

    public init(lat: Double, lon: Double) {
        self.lat = lat
        self.lon = lon
    }

    /// Mean Earth radius in kilometres (WGS-84).
    private static let earthRadiusKm: Double = 6371.0

    /// Returns the great-circle distance in kilometres between this location
    /// and `other` using the haversine formula.
    ///
    /// Accuracy is within ~0.3 % over the 1–25 km distances this app uses,
    /// which is sufficient for the radius values in `SearchRadius`.
    public func distance(to other: GeoLocation) -> Double {
        let r = GeoLocation.earthRadiusKm
        let lat1 = lat * .pi / 180.0
        let lat2 = other.lat * .pi / 180.0
        let dLat = (other.lat - lat) * .pi / 180.0
        let dLon = (other.lon - lon) * .pi / 180.0
        let sinHalfDLat = sin(dLat / 2)
        let sinHalfDLon = sin(dLon / 2)
        let a = sinHalfDLat * sinHalfDLat
            + cos(lat1) * cos(lat2) * sinHalfDLon * sinHalfDLon
        let c = 2.0 * atan2(a.squareRoot(), (1.0 - a).squareRoot())
        return r * c
    }
}

/// The four discovery-radius values a person can choose (AC#3).
///
/// The allowed values are exactly 1, 5, 10 and 25 kilometres, as stated in
/// the acceptance criterion.
///
/// The same values exist verbatim in the Kotlin lane (GeoLocation.kt) so that
/// both platforms enforce one shared set of choices (constitution P9).
public enum SearchRadius: Double {
    case one        = 1.0
    case five       = 5.0
    case ten        = 10.0
    case twentyFive = 25.0
}
