import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ProfileRepositoryTest {
    /**
     * A photo that passes validation: a supported format and a byte payload well
     * within [ProfileRepository.MAX_PHOTO_SIZE_BYTES]. The photo field is
     * mandatory, so every saved profile needs one; this keeps the tests focused
     * on the property under test rather than repeating photo boilerplate.
     */
    private fun validPhoto(
        bytes: ByteArray = byteArrayOf(1, 2, 3, 4),
        format: String = "png",
    ): ProfilePhoto = ProfilePhoto(bytes = bytes, format = format)

    @Test
    fun `saving a valid display name persists it for an independent read-back`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto()))

        val found = repository.find("user-1")
        assertEquals("Ada Lovelace", found?.displayName)
    }

    @Test
    fun `saving a blank display name throws and persists nothing`() {
        val repository = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = "   ", photo = validPhoto()))
        }
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `saving twice for the same id overwrites rather than duplicating`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Grace", photo = validPhoto()))
        repository.save(Profile(id = "user-1", displayName = "Grace Hopper", photo = validPhoto()))

        assertEquals("Grace Hopper", repository.find("user-1")?.displayName)
    }

    @Test
    fun `deleteAccount removes the stored profile so a later find returns null`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto()))

        assertTrue(repository.deleteAccount("user-1"))
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `deleteAccount on an unknown id returns false without throwing`() {
        val repository = ProfileRepository()

        assertFalse(repository.deleteAccount("never-saved"))
    }

    @Test
    fun `a display name exactly at the maximum length is accepted`() {
        val repository = ProfileRepository()
        val maxName = "a".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH)
        repository.save(Profile(id = "user-1", displayName = maxName, photo = validPhoto()))

        assertEquals(maxName, repository.find("user-1")?.displayName)
    }

    @Test
    fun `a display name one character over the maximum length throws and persists nothing`() {
        val repository = ProfileRepository()
        val tooLong = "a".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH + 1)

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = tooLong, photo = validPhoto()))
        }
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `a display name is stored without its surrounding whitespace`() {
        // The validation trimmed the name and the store kept the original, so
        // "  Ada  " passed a length check it did not actually satisfy and came
        // back with its padding intact. Every other test used clean input, so
        // the suite was green over it.
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "  Ada Lovelace  ", photo = validPhoto()))

        assertEquals("Ada Lovelace", repository.find("user-1")?.displayName)
    }

    @Test
    fun `a padded name at the limit is stored within the limit`() {
        val repository = ProfileRepository()
        val padded = "  " + "a".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH) + "  "
        repository.save(Profile(id = "user-1", displayName = padded, photo = validPhoto()))

        assertEquals(
            ProfileRepository.MAX_DISPLAY_NAME_LENGTH,
            repository.find("user-1")?.displayName?.length,
        )
    }

    @Test
    fun `saving a biography within the limit persists the trimmed value`() {
        val repository = ProfileRepository()
        repository.save(
            Profile(
                id = "user-1",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                biography = "  Mathematician and first programmer.  ",
            ),
        )

        assertEquals(
            "Mathematician and first programmer.",
            repository.find("user-1")?.biography,
        )
    }

    @Test
    fun `a biography one character over the maximum length throws and persists nothing`() {
        // AC-PROF-003-02: an over-limit biography is rejected before anything is
        // stored, and the error states the limit via MAX_BIOGRAPHY_LENGTH.
        val repository = ProfileRepository()
        val tooLong = "a".repeat(ProfileRepository.MAX_BIOGRAPHY_LENGTH + 1)

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(
                    id = "user-1",
                    displayName = "Ada Lovelace",
                    photo = validPhoto(),
                    biography = tooLong,
                ),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_BIOGRAPHY_LENGTH.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `deleteAccount removes the profile including its biography`() {
        val repository = ProfileRepository()
        repository.save(
            Profile(
                id = "user-1",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                biography = "Mathematician and first programmer.",
            ),
        )

        assertTrue(repository.deleteAccount("user-1"))
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `saving a valid photo persists it for an independent read-back`() {
        // AC-PROF-002-01: a supported-format, within-limit photo is accepted and
        // returned back — content-compared — by a separate find() read.
        val repository = ProfileRepository()
        val bytes = byteArrayOf(9, 8, 7, 6, 5)
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(bytes = bytes, format = "png")),
        )

        val found = repository.find("user-1")?.photo
        assertEquals("png", found?.format)
        assertTrue(bytes.contentEquals(found?.bytes ?: byteArrayOf()))
    }

    @Test
    fun `a photo format is stored normalized to lowercase and trimmed`() {
        // Mirrors the displayName-is-trimmed test: the format is validated after
        // normalization, so the stored value must be the normalized form too.
        val repository = ProfileRepository()
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(format = "  PNG  ")),
        )

        assertEquals("png", repository.find("user-1")?.photo?.format)
    }

    @Test
    fun `saving a photo with an unsupported format throws and persists nothing`() {
        // AC-PROF-002-02: the format is rejected before anything is stored, and
        // the error names at least one supported format.
        val repository = ProfileRepository()

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(format = "gif")))
        }
        assertTrue(ProfileRepository.SUPPORTED_PHOTO_FORMATS.any { error.message?.contains(it) == true })
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `saving a photo larger than the maximum size throws and persists nothing`() {
        // AC-PROF-002-03: an oversized photo is rejected before anything is
        // stored, and the error states the byte limit.
        val repository = ProfileRepository()
        val tooBig = ByteArray(ProfileRepository.MAX_PHOTO_SIZE_BYTES + 1)

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(bytes = tooBig)))
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_PHOTO_SIZE_BYTES.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `a photo exactly at the maximum size is accepted`() {
        val repository = ProfileRepository()
        val maxBytes = ByteArray(ProfileRepository.MAX_PHOTO_SIZE_BYTES)
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(bytes = maxBytes)),
        )

        assertEquals(ProfileRepository.MAX_PHOTO_SIZE_BYTES, repository.find("user-1")?.photo?.bytes?.size)
    }

    @Test
    fun `deleteAccount removes the profile including its photo`() {
        val repository = ProfileRepository()
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto()),
        )

        assertTrue(repository.deleteAccount("user-1"))
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `interests and activities exactly at their limits are accepted`() {
        // AC-PROF-021-01: a selection filled right up to each limit is valid —
        // the boundary count is allowed, not rejected — and persists intact.
        val repository = ProfileRepository()
        val interests = List(ProfileRepository.MAX_INTERESTS) { "interest-$it" }
        val activities = List(ProfileRepository.MAX_ACTIVITIES) { "activity-$it" }
        repository.save(
            Profile(
                id = "user-1",
                displayName = "Ada Lovelace",
                photo = validPhoto(),
                interests = interests,
                activities = activities,
            ),
        )

        val found = repository.find("user-1")
        assertEquals(interests, found?.interests)
        assertEquals(activities, found?.activities)
    }

    @Test
    fun `interests one entry over the maximum count throws and persists nothing`() {
        // AC-PROF-021-01: an over-limit interests list is rejected before
        // anything is stored, and the error states the limit via MAX_INTERESTS.
        val repository = ProfileRepository()
        val tooMany = List(ProfileRepository.MAX_INTERESTS + 1) { "interest-$it" }

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(
                    id = "user-1",
                    displayName = "Ada Lovelace",
                    photo = validPhoto(),
                    interests = tooMany,
                ),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_INTERESTS.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `activities one entry over the maximum count throws and persists nothing`() {
        // AC-PROF-021-01: an over-limit activities list is rejected before
        // anything is stored, and the error states the limit via MAX_ACTIVITIES.
        val repository = ProfileRepository()
        val tooMany = List(ProfileRepository.MAX_ACTIVITIES + 1) { "activity-$it" }

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(
                    id = "user-1",
                    displayName = "Ada Lovelace",
                    photo = validPhoto(),
                    activities = tooMany,
                ),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_ACTIVITIES.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `an at-limit interests list is accepted alongside an over-limit activities list being rejected`() {
        // AC-PROF-021-01: the two limits are enforced independently. A list at
        // the interests limit does not excuse an over-limit activities list, and
        // the activities failure is what rejects the save — nothing is stored.
        val repository = ProfileRepository()
        val interestsAtLimit = List(ProfileRepository.MAX_INTERESTS) { "interest-$it" }
        val activitiesOverLimit = List(ProfileRepository.MAX_ACTIVITIES + 1) { "activity-$it" }

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(
                    id = "user-1",
                    displayName = "Ada Lovelace",
                    photo = validPhoto(),
                    interests = interestsAtLimit,
                    activities = activitiesOverLimit,
                ),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_ACTIVITIES.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `an at-limit activities list is accepted alongside an over-limit interests list being rejected`() {
        // AC-PROF-021-01: the mirror case — a list at the activities limit does
        // not excuse an over-limit interests list, confirming each count is
        // checked on its own field and nothing is stored.
        val repository = ProfileRepository()
        val interestsOverLimit = List(ProfileRepository.MAX_INTERESTS + 1) { "interest-$it" }
        val activitiesAtLimit = List(ProfileRepository.MAX_ACTIVITIES) { "activity-$it" }

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(
                    id = "user-1",
                    displayName = "Ada Lovelace",
                    photo = validPhoto(),
                    interests = interestsOverLimit,
                    activities = activitiesAtLimit,
                ),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_INTERESTS.toString()) == true)
        assertNull(repository.find("user-1"))
    }
}
