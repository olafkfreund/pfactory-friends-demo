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
}
