// Reproduce the seeded input from the shared player's seed field.
module.exports = function playerSeed(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let bits = Math.imul(seed ^ (seed >>> 15), seed | 1);
    bits ^= bits + Math.imul(bits ^ (bits >>> 7), bits | 61);
    return ((bits ^ (bits >>> 14)) >>> 0) / 4294967296;
  };
};
