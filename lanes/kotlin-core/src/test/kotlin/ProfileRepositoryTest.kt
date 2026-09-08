import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ProfileRepositoryTest {
    @Test
    fun `saving a valid display name persists it for an independent read-back`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Ada Lovelace"))

        val found = repository.find("user-1")
        assertEquals("Ada Lovelace", found?.displayName)
    }

    @Test
    fun `saving a blank display name throws and persists nothing`() {
        val repository = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = "   "))
        }
        assertNull(repository.find("user-1"))
    }

    @Test
    fun `saving twice for the same id overwrites rather than duplicating`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Grace"))
        repository.save(Profile(id = "user-1", displayName = "Grace Hopper"))

        assertEquals("Grace Hopper", repository.find("user-1")?.displayName)
    }

    @Test
    fun `deleteAccount removes the stored profile so a later find returns null`() {
        val repository = ProfileRepository()
        repository.save(Profile(id = "user-1", displayName = "Ada Lovelace"))

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
        repository.save(Profile(id = "user-1", displayName = maxName))

        assertEquals(maxName, repository.find("user-1")?.displayName)
    }

    @Test
    fun `a display name one character over the maximum length throws and persists nothing`() {
        val repository = ProfileRepository()
        val tooLong = "a".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH + 1)

        assertFailsWith<IllegalArgumentException> {
            repository.save(Profile(id = "user-1", displayName = tooLong))
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
        repository.save(Profile(id = "user-1", displayName = "  Ada Lovelace  "))

        assertEquals("Ada Lovelace", repository.find("user-1")?.displayName)
    }

    @Test
    fun `a padded name at the limit is stored within the limit`() {
        val repository = ProfileRepository()
        val padded = "  " + "a".repeat(ProfileRepository.MAX_DISPLAY_NAME_LENGTH) + "  "
        repository.save(Profile(id = "user-1", displayName = padded))

        assertEquals(
            ProfileRepository.MAX_DISPLAY_NAME_LENGTH,
            repository.find("user-1")?.displayName?.length,
        )
    }
}
