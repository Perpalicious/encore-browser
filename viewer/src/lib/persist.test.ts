import { describe, it, expect } from 'vitest';
import { DEFAULT_VIEW_STATE, decodeHash, encodeHash, parseViewState } from './persist';

describe('persist — xscrapes', () => {
  it('defaults to no hidden scrapes', () => {
    expect(parseViewState({}).xscrapes).toEqual([]);
    expect(parseViewState(null).xscrapes).toEqual([]);
  });

  it('keeps only string entries from a hand-edited or stale value', () => {
    expect(parseViewState({ xscrapes: ['2026-09-15T22:30:00+00:00', 3, null] }).xscrapes)
      .toEqual(['2026-09-15T22:30:00+00:00']);
    expect(parseViewState({ xscrapes: 'nope' }).xscrapes).toEqual([]);
  });

  it('a pristine view produces an empty hash', () => {
    expect(encodeHash({ ...DEFAULT_VIEW_STATE })).toBe('');
  });

  it('round-trips through the hash', () => {
    const state = { ...DEFAULT_VIEW_STATE, xscrapes: ['2026-09-15T22:30:00+00:00'] };
    const hash = encodeHash(state);
    expect(hash).toContain('xscrapes');
    expect(decodeHash(hash)).toEqual(state);
  });
});
