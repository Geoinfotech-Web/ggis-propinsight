from aia_etl.sources.worldcover import worldcover_tile_urls


def test_worldcover_tiles_span_both_fct_latitude_tiles():
    urls = worldcover_tile_urls((6.779, 8.419, 7.724, 9.409))
    assert len(urls) == 2
    assert any("N06E006" in url for url in urls)
    assert any("N09E006" in url for url in urls)
