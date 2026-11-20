package store

// Store keeps items.
type Store struct {
	db *DB
}

type Cache struct {
	m map[string]string
}

func (s *Store) Get(id string) (Item, error) {
	return s.db.Get(id)
}

func (s *Store) Load(path string) {
	data, err := read(path)
	if err != nil {
	}
	s.db.Put(data)
}
