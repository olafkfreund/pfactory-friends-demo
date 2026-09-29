import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DiscoveryTest {

    private fun validPhoto(
        bytes: ByteArray = byteArrayOf(1, 2, 3, 4),
        format: String = "png",
    ): ProfilePhoto = ProfilePhoto(bytes = bytes, format = format)

    // MARK: - AC#4: ordered by score

    @Test
    fun `discover returns results ordered by score descending`() {
        // Searcher has jazz + climbing. Ada shares jazz (score 0.5),
        // Grace shares jazz + climbing (score 1.0). Grace must come first.
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz", "climbing"),
        )
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = listOf("jazz", "chess"),
                openToFriends = true,
            ),
        )
        repository.save(
            Profile(
                id = "grace",
                displayName = "Grace Hopper",
                photo = validPhoto(),
                interests = listOf("jazz", "climbing"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertEquals(2, results.size)
        assertEquals("grace", results[0].profile.id)
        assertEquals("ada", results[1].profile.id)
        assertEquals(1.0, results[0].score)
        assertEquals(0.5, results[1].score)
    }

    @Test
    fun `discover excludes the searcher even when they have openToFriends true`() {
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz"),
            openToFriends = true,
        )
        repository.save(searcher)
        repository.save(
            Profile(
                id = "other",
                displayName = "Other Person",
                photo = validPhoto(),
                interests = listOf("jazz"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertTrue(results.none { it.profile.id == "searcher" })
        assertEquals(1, results.size)
        assertEquals("other", results[0].profile.id)
    }

    @Test
    fun `discover excludes profiles with openToFriends false`() {
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz"),
        )
        repository.save(
            Profile(
                id = "closed",
                displayName = "Closed Profile",
                photo = validPhoto(),
                interests = listOf("jazz"),
                openToFriends = false,
            ),
        )

        val results = repository.discover(searcher)

        assertTrue(results.isEmpty())
    }

    @Test
    fun `discover returns an empty list when no open profiles exist`() {
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
        )

        val results = repository.discover(searcher)

        assertTrue(results.isEmpty())
    }

    // MARK: - AC#4: shows why each result was surfaced

    @Test
    fun `discover populates sharedInterests with the sorted intersection of interest tags`() {
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz", "climbing", "chess"),
        )
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = listOf("climbing", "jazz", "cycling"),
                openToFriends = true,
            ),
        )

        val result = repository.discover(searcher).first()

        // jazz and climbing overlap; sorted alphabetically
        assertEquals(listOf("climbing", "jazz"), result.sharedInterests)
    }

    @Test
    fun `discover populates sharedActivities with the sorted intersection of activity tags`() {
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            activities = listOf("weekends", "weekday-evenings"),
        )
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                activities = listOf("weekday-evenings", "mornings"),
                openToFriends = true,
            ),
        )

        val result = repository.discover(searcher).first()

        assertEquals(listOf("weekday-evenings"), result.sharedActivities)
    }

    @Test
    fun `discover returns empty sharedInterests and sharedActivities when there is no overlap`() {
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz"),
            activities = listOf("weekends"),
        )
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = listOf("chess"),
                activities = listOf("mornings"),
                openToFriends = true,
            ),
        )

        val result = repository.discover(searcher).first()

        assertTrue(result.sharedInterests.isEmpty())
        assertTrue(result.sharedActivities.isEmpty())
        assertEquals(0.0, result.score)
    }

    @Test
    fun `discover with empty searcher interests still returns open profiles with score zero`() {
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
        )
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = listOf("jazz"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertEquals(1, results.size)
        assertEquals(0.0, results[0].score)
    }

    @Test
    fun `discover score matches MatchScore output for the same inputs`() {
        // interests: mine={jazz,climbing}, theirs={jazz,chess} => 1/2 = 0.5
        // activities: mine={weekday-evenings}, theirs={weekday-evenings} => 1/1 = 1.0
        // combined = (0.5 + 1.0) / 2 = 0.75
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz", "climbing"),
            activities = listOf("weekday-evenings"),
        )
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = listOf("jazz", "chess"),
                activities = listOf("weekday-evenings"),
                openToFriends = true,
            ),
        )

        val result = repository.discover(searcher).first()

        assertEquals(0.75, result.score)
    }

    @Test
    fun `discover searcher without openToFriends can still browse open profiles`() {
        // The searcher does not need openToFriends=true to browse.
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz"),
            openToFriends = false,
        )
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = listOf("jazz"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertEquals(1, results.size)
        assertEquals("ada", results[0].profile.id)
    }

    // MARK: - AC#3: radius-based discovery
    //
    // Base location: lat=51.500, lon=-0.100 (central London, approx).
    // Offsets (same longitude, haversine on latitude arc only):
    //   +0.005° ≈  0.56 km  → inside 1 km, 5 km, 10 km, 25 km
    //   +0.040° ≈  4.45 km  → inside 5 km, 10 km, 25 km; outside 1 km
    //   +0.070° ≈  7.78 km  → inside 10 km, 25 km; outside 1 km, 5 km
    //   +0.150° ≈ 16.68 km  → inside 25 km; outside 1 km, 5 km, 10 km
    //   +0.300° ≈ 33.37 km  → outside all four radii

    private val baseLocation = GeoLocation(lat = 51.500, lon = -0.100)

    private fun locationAt(deltaLat: Double) = GeoLocation(lat = 51.500 + deltaLat, lon = -0.100)

    @Test
    fun `discover with radius returns only profiles within that radius`() {
        // ada is ~0.56 km away, grace is ~4.45 km away.
        // A 1 km radius should include only ada; a 5 km radius should include both.
        val repository = ProfileRepository()
        val searcher = Profile(id = "searcher", displayName = "Searcher", photo = validPhoto())
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                openToFriends = true,
                location = locationAt(0.005),   // ~0.56 km
            ),
        )
        repository.save(
            Profile(
                id = "grace",
                displayName = "Grace Hopper",
                photo = validPhoto(),
                openToFriends = true,
                location = locationAt(0.040),   // ~4.45 km
            ),
        )

        val within1km = repository.discover(searcher, baseLocation, SearchRadius.ONE)
        val within5km = repository.discover(searcher, baseLocation, SearchRadius.FIVE)

        assertEquals(1, within1km.size)
        assertEquals("ada", within1km[0].profile.id)
        assertEquals(2, within5km.size)
    }

    @Test
    fun `discover with radius excludes profiles without a location`() {
        // A profile that has never reported its location cannot be placed within
        // any radius and must be excluded from radius-filtered results.
        val repository = ProfileRepository()
        val searcher = Profile(id = "searcher", displayName = "Searcher", photo = validPhoto())
        repository.save(
            Profile(
                id = "no-location",
                displayName = "No Location",
                photo = validPhoto(),
                openToFriends = true,
                // location deliberately omitted (defaults to null)
            ),
        )

        val results = repository.discover(searcher, baseLocation, SearchRadius.TWENTY_FIVE)

        assertTrue(results.isEmpty())
    }

    @Test
    fun `discover with radius still honours the openToFriends gate`() {
        // A profile that is within the radius but has openToFriends=false must
        // not appear in radius-filtered results.
        val repository = ProfileRepository()
        val searcher = Profile(id = "searcher", displayName = "Searcher", photo = validPhoto())
        repository.save(
            Profile(
                id = "closed",
                displayName = "Closed Profile",
                photo = validPhoto(),
                openToFriends = false,          // flag is off
                location = locationAt(0.005),   // well within any radius
            ),
        )

        val results = repository.discover(searcher, baseLocation, SearchRadius.TWENTY_FIVE)

        assertTrue(results.isEmpty())
    }

    @Test
    fun `discover with radius results are ordered by score descending`() {
        // Two profiles within the radius; higher-scoring one must come first.
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = validPhoto(),
            interests = listOf("jazz", "climbing"),
        )
        // grace shares both interests → score 1.0
        repository.save(
            Profile(
                id = "grace",
                displayName = "Grace Hopper",
                photo = validPhoto(),
                interests = listOf("jazz", "climbing"),
                openToFriends = true,
                location = locationAt(0.005),   // ~0.56 km
            ),
        )
        // ada shares only jazz → score 0.5
        repository.save(
            Profile(
                id = "ada",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = listOf("jazz"),
                openToFriends = true,
                location = locationAt(0.040),   // ~4.45 km
            ),
        )

        val results = repository.discover(searcher, baseLocation, SearchRadius.TEN)

        assertEquals(2, results.size)
        assertEquals("grace", results[0].profile.id)
        assertEquals(1.0, results[0].score)
        assertEquals("ada", results[1].profile.id)
        assertEquals(0.5, results[1].score)
    }

    @Test
    fun `discover with all four radius values uses the correct thresholds`() {
        // One profile per zone; each radius value should include exactly the
        // profiles within it.
        //   ~0.56 km → within all four radii
        //   ~4.45 km → within 5 km, 10 km, 25 km; outside 1 km
        //   ~7.78 km → within 10 km, 25 km; outside 1 km, 5 km
        //  ~16.68 km → within 25 km; outside 1 km, 5 km, 10 km
        val repository = ProfileRepository()
        val searcher = Profile(id = "searcher", displayName = "Searcher", photo = validPhoto())
        repository.save(Profile(id = "p1", displayName = "P1", photo = validPhoto(), openToFriends = true, location = locationAt(0.005)))
        repository.save(Profile(id = "p2", displayName = "P2", photo = validPhoto(), openToFriends = true, location = locationAt(0.040)))
        repository.save(Profile(id = "p3", displayName = "P3", photo = validPhoto(), openToFriends = true, location = locationAt(0.070)))
        repository.save(Profile(id = "p4", displayName = "P4", photo = validPhoto(), openToFriends = true, location = locationAt(0.150)))

        assertEquals(1, repository.discover(searcher, baseLocation, SearchRadius.ONE).size)
        assertEquals(2, repository.discover(searcher, baseLocation, SearchRadius.FIVE).size)
        assertEquals(3, repository.discover(searcher, baseLocation, SearchRadius.TEN).size)
        assertEquals(4, repository.discover(searcher, baseLocation, SearchRadius.TWENTY_FIVE).size)
    }

    // MARK: - AC#1 / constitution P3: age-bracket isolation in discovery

    @Test
    fun `discover excludes adult candidates from a minor searcher`() {
        // A 17-year-old searcher must not see 18+ profiles in their results.
        // Constitution P3 (enforceable): discovery is age-isolated so that
        // minors (age < MIN_ADULT_AGE) are never surfaced to adults and vice
        // versa.
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "minor-searcher",
            displayName = "Minor Searcher",
            photo = validPhoto(),
            age = 17,
            interests = listOf("jazz"),
        )
        repository.save(
            Profile(
                id = "adult",
                displayName = "Adult User",
                photo = validPhoto(),
                age = ProfileRepository.MIN_ADULT_AGE,
                interests = listOf("jazz"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertTrue(results.isEmpty())
    }

    @Test
    fun `discover excludes minor candidates from an adult searcher`() {
        // An 18-year-old searcher must not see under-18 profiles in their results.
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "adult-searcher",
            displayName = "Adult Searcher",
            photo = validPhoto(),
            age = ProfileRepository.MIN_ADULT_AGE,
            interests = listOf("jazz"),
        )
        repository.save(
            Profile(
                id = "minor",
                displayName = "Minor User",
                photo = validPhoto(),
                age = 17,
                interests = listOf("jazz"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertTrue(results.isEmpty())
    }

    @Test
    fun `discover shows minor candidates to a minor searcher`() {
        // A 16-year-old sees other under-18 profiles (both are minors).
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "minor-16",
            displayName = "Minor 16",
            photo = validPhoto(),
            age = 16,
            interests = listOf("jazz"),
        )
        repository.save(
            Profile(
                id = "minor-17",
                displayName = "Minor 17",
                photo = validPhoto(),
                age = 17,
                interests = listOf("jazz"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertEquals(1, results.size)
        assertEquals("minor-17", results[0].profile.id)
    }

    @Test
    fun `discover shows adult candidates to an adult searcher`() {
        // An 18-year-old sees other 18+ profiles (both are adults).
        val repository = ProfileRepository()
        val searcher = Profile(
            id = "adult-18",
            displayName = "Adult 18",
            photo = validPhoto(),
            age = ProfileRepository.MIN_ADULT_AGE,
            interests = listOf("jazz"),
        )
        repository.save(
            Profile(
                id = "adult-25",
                displayName = "Adult 25",
                photo = validPhoto(),
                age = 25,
                interests = listOf("jazz"),
                openToFriends = true,
            ),
        )

        val results = repository.discover(searcher)

        assertEquals(1, results.size)
        assertEquals("adult-25", results[0].profile.id)
    }
}
