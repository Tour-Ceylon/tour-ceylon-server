from types import SimpleNamespace
from uuid import uuid4

from app.repositories.listing_repo import ListingRepository
from app.schemas.listing_schema import ListingSearchParams


class FakeIdQuery:
    def __init__(self, paged_ids, total_count):
        self.paged_ids = paged_ids
        self.total_count = total_count
        self.distinct_calls = 0
        self.offset_value = None
        self.limit_value = None

    def options(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def with_entities(self, *args, **kwargs):
        return self

    def scalar(self):
        return self.total_count

    def distinct(self):
        self.distinct_calls += 1
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return [(listing_id,) for listing_id in self.paged_ids]


class FakeHydrationQuery:
    def __init__(self, listings):
        self.listings = listings
        self.filter_calls = 0

    def filter(self, *args, **kwargs):
        self.filter_calls += 1
        return self

    def all(self):
        return list(self.listings)


def test_search_uses_distinct_ids_then_hydrates_full_listings():
    first_id = uuid4()
    second_id = uuid4()
    id_query = FakeIdQuery([second_id, first_id], total_count=2)
    hydrated_query = FakeHydrationQuery(
        [
            SimpleNamespace(id=first_id, title="First"),
            SimpleNamespace(id=second_id, title="Second"),
        ]
    )

    repo = ListingRepository.__new__(ListingRepository)
    repo.db = SimpleNamespace(query=lambda *args, **kwargs: id_query)
    repo._list_query = lambda: hydrated_query

    listings, total = repo.search(
        ListingSearchParams(
            adults=2,
            children=0,
            page=1,
            per_page=100,
        )
    )

    assert total == 2
    assert [listing.id for listing in listings] == [second_id, first_id]
    assert id_query.distinct_calls == 1
    assert id_query.offset_value == 0
    assert id_query.limit_value == 100
    assert hydrated_query.filter_calls == 1
