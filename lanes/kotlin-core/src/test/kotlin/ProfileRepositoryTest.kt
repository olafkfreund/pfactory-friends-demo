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

    /**
     * An age that passes validation: exactly [ProfileRepository.MIN_AGE], the
     * confirmed 16+ boundary. The age field is mandatory, so every saved profile
     * needs one; this keeps the tests focused on the property under test rather
     * than repeating age boilerplate. Mirrors [validPhoto].
     */
    private fun validAge(): Int = ProfileRepository.MIN_AGE

    @Test
    fun `saving a valid display name persists it for an independent read-back`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = validAge()))

        val found = repository.find("user-1")
        assertEquals("Ada Lovelace", found?.displayName)
    }

    @Test
    fun `saving a blank id throws and persists nothing`() {
        // AC for issue #36, item 1: an empty id is rejected rather than
        // silently storing a profile under the "" key.
        val repository = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "", displayName = "Ada Lovelace", photo = validPhoto()))
        }
        assertNull(repository.find(""))
    }

    @Test
    fun `saving a whitespace-only id throws and persists nothing`() {
        // AC for issue #36, item 1: "   " is whitespace, not a real id.
        val repository = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "   ", displayName = "Ada Lovelace", photo = validPhoto()))
        }
        assertNull(repository.find("   "))
    }

    @Test
    fun `saving a blank display name throws and persists nothing`() {
        val repository = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = "   ", photo = validPhoto(), age = validAge()))
        }
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `saving twice for the same id overwrites rather than duplicating`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Grace", photo = validPhoto(), age = validAge()))
        repository.save(Profile(id = "user-1", displayName = "Grace Hopper", photo = validPhoto(), age = validAge()))

        assertEquals("Grace Hopper", repository.find("user-1")?.displayName)
    }

    @Test
    fun `deleteAccount removes the stored profile so a later find returns null`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = validAge()))

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
        repository.save(Profile(id = "user-1", displayName = maxName, photo = validPhoto(), age = validAge()))

        assertEquals(maxName, repository.find("user-1")?.displayName)
    }

    @Test
    fun `a display name one character over the maximum length throws and persists nothing`() {
        val repository = ProfileRepository()
        val tooLong = "a".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH + 1)

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = tooLong, photo = validPhoto(), age = validAge()))
        }
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `a display name containing a newline throws and persists nothing`() {
        // AC for issue #36, item 2: a newline is a display-spoofing / log
        // -injection surface once the name is rendered in lists, notifications
        // and logs.
        val repository = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = "Ada\nLovelace", photo = validPhoto()))
        }
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `a display name containing a carriage return throws and persists nothing`() {
        val repository = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = "Ada\rLovelace", photo = validPhoto()))
        }
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `a display name of 50 simple emoji at the maximum length is accepted`() {
        // AC for issue #36, item 3: with the length measured in UTF-16 code
        // units, 50 emoji (100 units) were wrongly rejected. Measured in code
        // points, 50 single-code-point emoji is exactly the limit.
        val repository = ProfileRepository()
        val fiftyEmoji = "😀".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH)

        repository.save(Profile(id = "user-1", displayName = fiftyEmoji, photo = validPhoto()))

        assertEquals(fiftyEmoji, repository.find("user-1")?.displayName)
    }

    @Test
    fun `a display name of 51 simple emoji over the maximum length throws`() {
        val repository = ProfileRepository()
        val fiftyOneEmoji = "😀".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH + 1)

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = fiftyOneEmoji, photo = validPhoto()))
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
        repository.save(Profile(id = "user-1", displayName = "  Ada Lovelace  ", photo = validPhoto(), age = validAge()))

        assertEquals("Ada Lovelace", repository.find("user-1")?.displayName)
    }

    @Test
    fun `a padded name at the limit is stored within the limit`() {
        val repository = ProfileRepository()
        val padded = "  " + "a".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH) + "  "
        repository.save(Profile(id = "user-1", displayName = padded, photo = validPhoto(), age = validAge()))

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
                age = validAge(),
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
                    age = validAge(),
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
                age = validAge(),
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
            Profile(
                id = "user-1",
                displayName = "Ada Lovelace",
                photo = validPhoto(bytes = bytes, format = "png"),
                age = validAge(),
            ),
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
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(format = "  PNG  "), age = validAge()),
        )

        assertEquals("png", repository.find("user-1")?.photo?.format)
    }

    @Test
    fun `saving a photo with an unsupported format throws and persists nothing`() {
        // AC-PROF-002-02: the format is rejected before anything is stored, and
        // the error names at least one supported format.
        val repository = ProfileRepository()

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(format = "gif"), age = validAge()),
            )
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
            repository.save(
                Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(bytes = tooBig), age = validAge()),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_PHOTO_SIZE_BYTES.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `a photo exactly at the maximum size is accepted`() {
        val repository = ProfileRepository()
        val maxBytes = ByteArray(ProfileRepository.MAX_PHOTO_SIZE_BYTES)
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(bytes = maxBytes), age = validAge()),
        )

        assertEquals(ProfileRepository.MAX_PHOTO_SIZE_BYTES, repository.find("user-1")?.photo?.bytes?.size)
    }

    @Test
    fun `deleteAccount removes the profile including its photo`() {
        val repository = ProfileRepository()
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = validAge()),
        )

        assertTrue(repository.deleteAccount("user-1"))
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `saving a valid age persists it for an independent read-back`() {
        // AC-PROF-004-01: an age at or above MIN_AGE is accepted and returned by
        // a separate find() read.
        val repository = ProfileRepository()
        val age = ProfileRepository.MIN_AGE + 10
        repository.save(Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = age))

        assertEquals(age, repository.find("user-1")?.age)
    }

    @Test
    fun `an age exactly at the minimum is accepted`() {
        // AC-PROF-004-01: the 16+ boundary is inclusive, so exactly MIN_AGE is
        // accepted and persisted.
        val repository = ProfileRepository()
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = ProfileRepository.MIN_AGE),
        )

        assertEquals(ProfileRepository.MIN_AGE, repository.find("user-1")?.age)
    }

    @Test
    fun `an age below the minimum throws and persists nothing`() {
        // AC-PROF-004-02: an under-age profile is rejected before anything is
        // stored, and the error states the minimum via MIN_AGE.
        val repository = ProfileRepository()
        val tooYoung = ProfileRepository.MIN_AGE - 1

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = tooYoung),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MIN_AGE.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `an age above the maximum throws and persists nothing`() {
        // Guards the MAX_AGE placeholder plausibility bound: an implausibly large
        // numeric age is rejected before anything is stored, and the error states
        // the maximum via MAX_AGE.
        //
        // Note: AC-PROF-004-03 (non-numeric age) is not naturally coverable at
        // this layer because Profile.age is a compile-time Int — the type system
        // already prevents non-numeric values from ever reaching save().
        val repository = ProfileRepository()
        val tooOld = ProfileRepository.MAX_AGE + 1

        val error = assertFailsWith<IllegalArgumentException> {
            repository.save(
                Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = tooOld),
            )
        }
        assertTrue(error.message?.contains(ProfileRepository.MAX_AGE.toString()) == true)
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `deleteAccount removes the profile including its age`() {
        val repository = ProfileRepository()
        repository.save(
            Profile(id = "user-1", displayName = "Ada Lovelace", photo = validPhoto(), age = validAge()),
        )

        assertTrue(repository.deleteAccount("user-1"))
        assertNull(repository.find("user-1"))
    }
}
