import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull

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
}
