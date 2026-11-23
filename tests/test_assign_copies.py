"""One release track on several discs of the album: a Blu-ray with the same songs in several mixes (ADR 0102)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright
from pipeline import fixtags

from .conftest import MakeFlac

# Phil Collins, Face Value (Discogs 38461926) in small: the release lists the songs once per mix heading, all on
# disc 1; the album has a disc per mix.
TITLES = ('In The Air Tonight', 'This Must Be Love')
MIXES = ('2026 Atmos Mix', '2026 Stereo Mix', 'Original 1981 Stereo Mix - 2015 Remaster')
REL = {
	'id': '888',
	'title': 'Face Value',
	'artist': 'Phil Collins',
	'year': 2026,
	'catno': 'X',
	'master_id': 0,
	'image': '',
	'tracks': [
		{
			'i': i,
			'position': str(i + 1),
			'disc': 1,
			'track': i + 1,
			'title': TITLES[i % 2],
			'duration': 0,
			'part_of': '',
			'artist': 'Phil Collins',
			'credits': {},
			'subtitle': '2026 Atmos Mix - 2026 Stereo Mix'
			if i < 2
			else 'Original 1981 Stereo Mix - 2015 Remaster',
		}
		for i in range(4)
	],
}


@pytest.fixture
def blu_ray(make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch) -> Path:
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: REL)
	monkeypatch.setitem(tagwright.raw_releases, '888', {'id': 888, 'title': 'Face Value'})
	monkeypatch.setattr(tagwright, 'fix_album', lambda path, cfg: fixtags.FixResult(2, 'X', 'V'))
	folder = tagwright.ROOT / 'Face Value'
	n = 0
	for d, mix in enumerate(MIXES, 1):
		for title in TITLES:
			n += 1  # numbered through the whole album, as the rip came
			make_flac(
				folder / f'Disc {d}' / f'{d:02d}_{n:02d}.flac',
				TITLE=title,
				DISCNUMBER=str(d),
				TRACKNUMBER=str(n),
				**{'SET SUBTITLE': mix},
			)
	return folder


def test_propose_gives_every_disc_of_the_album_the_songs(client: TestClient, blu_ray: Path) -> None:
	r = client.post('/api/tracks/propose', json={'path': str(blu_ray), 'release_id': '888'}).json()
	got = [(f['file'].split('/')[0], f['rel']) for f in r['files']]
	# discs 1 and 2 take the first heading's songs, disc 3 the second's (its subtitle); each disc in turn
	assert got == [
		('Disc 1', 0),
		('Disc 1', 1),
		('Disc 2', 0),
		('Disc 2', 1),
		('Disc 3', 2),
		('Disc 3', 3),
	]


def test_apply_numbers_every_disc_from_one(client: TestClient, blu_ray: Path) -> None:
	files = [str(f.relative_to(blu_ray)) for f in tagwright.flacs(blu_ray)]
	rels = [0, 1, 0, 1, 2, 3]
	r = client.post(
		'/api/tracks/apply',
		json={
			'path': str(blu_ray),
			'release_id': '888',
			'import_titles': True,
			'assignments': [{'file': f, 'rel': i} for f, i in zip(files, rels, strict=True)],
		},
	)
	assert r.status_code == 200, r.text
	got = sorted(
		(FLAC(f)['DISCNUMBER'][0], FLAC(f)['TRACKNUMBER'][0], FLAC(f)['TITLE'][0])
		for f in blu_ray.rglob('*.flac')
	)
	assert got == [(str(d), str(t), TITLES[t - 1]) for d in (1, 2, 3) for t in (1, 2)]


def test_one_release_track_twice_on_one_disc_is_refused(client: TestClient, blu_ray: Path) -> None:
	files = [str(f.relative_to(blu_ray)) for f in tagwright.flacs(blu_ray)][:2]
	r = client.post(
		'/api/tracks/apply',
		json={
			'path': str(blu_ray),
			'release_id': '888',
			'assignments': [{'file': f, 'rel': 0} for f in files],
		},
	)
	assert r.status_code == 400
	assert 'twice on one disc' in r.text


def test_an_album_without_reuse_keeps_the_release_discs() -> None:
	rel = {'tracks': [{'disc': 1}, {'disc': 2}]}
	_, _, final, _, _ = tagwright.number_assignments(
		rel, [{'file': 'a', 'rel': 0}, {'file': 'b', 'rel': 1}], {'a': 5, 'b': 5}
	)
	assert final == {'a': (1, 1), 'b': (2, 1)}


def test_mixes_listed_as_one_disc_follow_the_album_discs_and_take_medley_parts(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""ADR 0109, shaped like The Alan Parsons Project, Tales Of Mystery And Imagination (Discogs 9448188): two mixes
	under two headings on one release disc, each with a medley in parts; the album has a disc per mix, numbered
	1..n. Before, disc 1's track 2 took the other mix's track 2 (the disc/track bonus), the part files took the whole
	medley, and everything was numbered on disc 1."""
	mixes = ('5.1 Mix', 'Original Stereo Mix')
	tracks, i = [], 0
	for m, mix in enumerate(mixes):
		for n, (title, dur, parts) in enumerate(
			(('Raven', 238, ()), ('Usher', 330, (('Prelude', 120), ('Fall', 210))))
		):
			tracks.append(
				{
					'i': i,
					'position': str(m * 2 + n + 1),
					'disc': 1,
					'track': m * 2 + n + 1,
					'title': title,
					'duration': dur,
					'part_of': '',
					'subtitle': mix,
					'artist': 'A',
					'credits': {},
				}
			)
			i += 1
			for part, pdur in parts:
				tracks.append(
					{
						'i': i,
						'position': f'{m * 2 + n + 1}.{len(tracks)}',
						'disc': 1,
						'track': m * 2 + n + 1,
						'title': part,
						'duration': pdur,
						'part_of': title,
						'subtitle': mix,
						'artist': 'A',
						'credits': {},
					}
				)
				i += 1
	rel = {
		'id': '9',
		'title': 'Tales',
		'artist': 'A',
		'year': 2016,
		'catno': 'X',
		'master_id': 0,
		'image': '',
		'tracks': tracks,
	}
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: rel)
	folder = tagwright.ROOT / 'Tales'
	# album disc 1 is the stereo mix, disc 2 the 5.1 mix (the opposite order of the release)
	for d, mix in ((1, 'Original Stereo Mix Of Album'), (2, 'DTS 5.1 Surround Mix')):
		for n, title in enumerate(('Raven', 'Usher (Prelude)', 'Usher (Fall)'), 1):
			make_flac(
				folder / f'Disc {d}' / f'{d:02d}_{n:02d}.flac',
				TITLE=title,
				DISCNUMBER=str(d),
				TRACKNUMBER=str(n),
				**{'SET SUBTITLE': mix},
			)
	r = client.post('/api/tracks/propose', json={'path': str(folder), 'release_id': '9'}).json()
	got = [(f['file'], tracks[f['rel']]['subtitle'], tracks[f['rel']]['title']) for f in r['files']]
	assert got == [
		('Disc 1/01_01.flac', 'Original Stereo Mix', 'Raven'),
		('Disc 1/01_02.flac', 'Original Stereo Mix', 'Prelude'),
		('Disc 1/01_03.flac', 'Original Stereo Mix', 'Fall'),
		('Disc 2/02_01.flac', '5.1 Mix', 'Raven'),
		('Disc 2/02_02.flac', '5.1 Mix', 'Prelude'),
		('Disc 2/02_03.flac', '5.1 Mix', 'Fall'),
	]
	_, _, final, _, _ = tagwright.number_assignments(
		rel,
		[{'file': f['file'], 'rel': f['rel']} for f in r['files']],
		{f['file']: f['disc'] for f in r['files']},
	)
	assert [final[f['file']] for f in r['files']] == [
		(1, 1),
		(1, 2),
		(1, 3),
		(2, 1),
		(2, 2),
		(2, 3),
	]
	# ADR 0110: Import song titles gives a part "Medley (Part)"
	monkeypatch.setitem(tagwright.raw_releases, '9', {'id': 9, 'title': 'Tales'})
	monkeypatch.setattr(tagwright, 'fix_album', lambda path, cfg: fixtags.FixResult(2, 'X', 'V'))
	res = client.post(
		'/api/tracks/apply',
		json={
			'path': str(folder),
			'release_id': '9',
			'import_titles': True,
			'assignments': [{'file': f['file'], 'rel': f['rel']} for f in r['files']],
		},
	)
	assert res.status_code == 200, res.text
	titles = sorted(FLAC(f)['TITLE'][0] for f in (folder / 'Disc 1').glob('*.flac'))
	assert titles == ['Raven', 'Usher (Fall)', 'Usher (Prelude)']
