#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <gmp.h>

/* -------- helpers -------- */

/* floor(log_p(x)) for x>0, p>=2 */
static inline int ilogp_int(int x, int p) {
    if (x <= 0) return 0;
    int lm = 0;
    while (x >= p) {
        x /= p;
        lm++;
    }
    return lm;
}

/* Build OR-mask for bit interval [lo, hi] and OR into dst:
   dst |= ((2^len - 1) << lo) */
static inline void mpz_or_range(mpz_t dst, unsigned lo, unsigned hi,
                               mpz_t tmp_pow, mpz_t tmp_interval) {
    if (hi < lo) return;
    unsigned len = hi - lo + 1;

    /* Bitset logic is base-2 regardless of p. */
    mpz_ui_pow_ui(tmp_pow, 2u, (unsigned long)len);   // 2^len
    mpz_sub_ui(tmp_interval, tmp_pow, 1u);            // 2^len - 1
    mpz_mul_2exp(tmp_interval, tmp_interval, (mp_bitcnt_t)lo); // << lo
    mpz_ior(dst, dst, tmp_interval);
}

/* Hash mpz by mixing its limbs. */
static inline uint64_t mix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 37)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

static uint64_t mpz_hash64(const mpz_t z) {
    /* Only nonnegative keys are used here (u is odd positive). */
    size_t nlimbs = mpz_size(z);
    uint64_t h = mix64((uint64_t)nlimbs);

    /* Sample limbs; for huge numbers hashing every limb is expensive.
       This samples first few and last few limbs to keep it fast-ish. */
    const size_t S = 4;
    size_t take_front = nlimbs < S ? nlimbs : S;
    for (size_t i = 0; i < take_front; i++) {
        mp_limb_t limb = mpz_getlimbn(z, (mp_size_t)i);
        h ^= mix64((uint64_t)limb + 0x100000001b3ULL * (uint64_t)i);
    }
    if (nlimbs > S) {
        size_t take_back = (nlimbs - take_front) < S ? (nlimbs - take_front) : S;
        for (size_t j = 0; j < take_back; j++) {
            size_t i = nlimbs - 1 - j;
            mp_limb_t limb = mpz_getlimbn(z, (mp_size_t)i);
            h ^= mix64((uint64_t)limb + 0x9e3779b97f4a7c15ULL * (uint64_t)i);
        }
    }
    return h;
}

/* -------- hash table: mpz key -> mpz mask -------- */

typedef struct {
    int used;      // 0 empty, 1 used
    mpz_t key;     // odd u
    mpz_t mask;    // bitset of t's
} Entry;

typedef struct {
    Entry *tab;
    size_t cap;    // power of two
    size_t size;   // used entries
} UMap;

static void umap_init(UMap *m, size_t cap_pow2) {
    m->cap = cap_pow2;
    m->size = 0;
    m->tab = (Entry *)calloc(m->cap, sizeof(Entry));
    if (!m->tab) { perror("calloc"); exit(1); }
}

static void umap_destroy(UMap *m) {
    for (size_t i = 0; i < m->cap; i++) {
        if (m->tab[i].used) {
            mpz_clear(m->tab[i].key);
            mpz_clear(m->tab[i].mask);
        }
    }
    free(m->tab);
    m->tab = NULL;
    m->cap = m->size = 0;
}

static void umap_rehash(UMap *m, size_t new_cap) {
    Entry *old = m->tab;
    size_t oldcap = m->cap;

    m->tab = (Entry *)calloc(new_cap, sizeof(Entry));
    if (!m->tab) { perror("calloc"); exit(1); }
    m->cap = new_cap;
    m->size = 0;

    for (size_t i = 0; i < oldcap; i++) {
        if (!old[i].used) continue;

        uint64_t h = mpz_hash64(old[i].key);
        size_t idx = (size_t)h & (m->cap - 1);
        while (m->tab[idx].used) idx = (idx + 1) & (m->cap - 1);

        m->tab[idx].used = 1;
        mpz_init(m->tab[idx].key);
        mpz_init(m->tab[idx].mask);
        mpz_set(m->tab[idx].key, old[i].key);
        mpz_set(m->tab[idx].mask, old[i].mask);
        m->size++;

        mpz_clear(old[i].key);
        mpz_clear(old[i].mask);
    }
    free(old);
}

/* Return pointer to mask for key u; create if missing. */
static mpz_t *umap_get_or_create(UMap *m, const mpz_t u) {
    // Grow around load factor 0.7
    if ((m->size + 1) * 10 >= m->cap * 7) {
        /* cap MUST remain power-of-two for idx = h & (cap-1) probing */
        umap_rehash(m, m->cap * 2);
    }

    uint64_t h = mpz_hash64(u);
    size_t idx = (size_t)h & (m->cap - 1);

    while (m->tab[idx].used) {
        if (mpz_cmp(m->tab[idx].key, u) == 0) {
            return &m->tab[idx].mask;
        }
        idx = (idx + 1) & (m->cap - 1);
    }

    m->tab[idx].used = 1;
    mpz_init(m->tab[idx].key);
    mpz_init_set_ui(m->tab[idx].mask, 0);
    mpz_set(m->tab[idx].key, u);
    m->size++;
    return &m->tab[idx].mask;
}

/* -------- main computation -------- */

void A_ads_size_big(int n, int p, mpz_t A_size, mpz_t AA_size) {
    mpz_set_ui(A_size, 0);
    mpz_set_ui(AA_size, 0);

    /* Collect reduced i's: those i in [1..n] with p ∤ i */
    int *units = (int *)malloc((size_t)n * sizeof(int));
    int *Emax  = (int *)malloc((size_t)n * sizeof(int));
    if (!units || !Emax) { perror("malloc"); exit(1); }

    int num_units = 0;
    for (int i = 1; i <= n; i++) {
        if (i % p != 0) units[num_units++] = i;
    }

    for (int i = 0; i < num_units; i++) {
        int u = units[i];
        int q = n / u;
        int L = ilogp_int(q, p);
        Emax[i] = n + L;
    }

    for (int i = 0; i < num_units; i++) {
        mpz_add_ui(A_size, A_size, (unsigned long)Emax[i]);
    }

    printf("n = %d: |A| = ", n);
    mpz_out_str(stdout, 10, A_size);
    printf("\n");
    fflush(stdout);

    // Map u -> mask
    UMap map;
    umap_init(&map, 1u << 13); // 8192 start; grows as needed

    // Temporaries
    mpz_t aZ, bZ, pZ, pPow, K, uZ, tmp_pow, tmp_interval;
    mpz_init(aZ);
    mpz_init(bZ);
    mpz_init_set_ui(pZ, (unsigned long)p);
    mpz_init(pPow);
    mpz_init(K);
    mpz_init(uZ);
    mpz_init(tmp_pow);
    mpz_init(tmp_interval);

    for (int ai = 0; ai < num_units; ai++) {
        int a = units[ai];
        int Ea = Emax[ai];
        mpz_set_ui(aZ, (unsigned long)a);

        for (int bi = 0; bi < num_units; bi++) {
            int b = units[bi];
            int Eb = Emax[bi];
            mpz_set_ui(bZ, (unsigned long)b);

            int max_d = Eb - 1;
            if (max_d < 0) continue;

            for (int d = 0; d <= max_d; d++) {
                int Eb_minus_d = Eb - d;
                int E1max = (Ea < Eb_minus_d) ? Ea : Eb_minus_d;
                if (E1max < 1) break;

                // K = a + (b << d) as big-int
                mpz_ui_pow_ui(pPow, (unsigned long)p, (unsigned long)d); // p^d
                mpz_mul(K, bZ, pPow);                                    // b * p^d
                mpz_add(K, K, aZ);                                       // a + b*p^d

                // tz = vp(K) = number of trailing zeros in K
                mp_bitcnt_t tz = 0;
                while (mpz_divisible_p(K, pZ)) {
                    mpz_divexact(K, K, pZ);
                    tz++;
                }

                // u = K >> tz
                mpz_set(uZ, K); // after removing p^tz, K already equals u

                unsigned t_lo = (unsigned)(1 + tz);
                unsigned t_hi = (unsigned)(E1max + (int)tz);

                mpz_t *maskp = umap_get_or_create(&map, uZ);
                mpz_or_range(*maskp, t_lo, t_hi, tmp_pow, tmp_interval);
            }
        }
    }

    // Sum popcounts
    for (size_t i = 0; i < map.cap; i++) {
        if (!map.tab[i].used) continue;
        size_t bits = mpz_popcount(map.tab[i].mask);
        mpz_add_ui(AA_size, AA_size, (unsigned long)bits);
    }

    printf("n = %d: |A+A| = ", n);
    mpz_out_str(stdout, 10, AA_size);
    printf("\n");
    fflush(stdout);

    // Cleanup
    mpz_clear(aZ);
    mpz_clear(bZ);
    mpz_clear(pZ);
    mpz_clear(pPow);
    mpz_clear(K);
    mpz_clear(uZ);
    mpz_clear(tmp_pow);
    mpz_clear(tmp_interval);

    umap_destroy(&map);
    free(units);
    free(Emax);
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <p> <n>\n", argv[0]);
        return 1;
    }

    int p = atoi(argv[1]);
    int n = atoi(argv[2]);
    if (n < 1) {
        fprintf(stderr, "Error: n must be a positive integer\n");
        return 1;
    }
    if (p < 2) {
        fprintf(stderr, "Error: p must be an integer >= 2\n");
        return 1;
    }

    mpz_t A_size, AA_size;
    mpz_init(A_size);
    mpz_init(AA_size);

    printf("Computing for n = %d, p = %d...\n", n, p);;
    A_ads_size_big(n, p, A_size, AA_size);

    printf("\nFinal Results for p:\n");
    printf("n, |A|, |A+A|\n");
    printf("%d, ", n);
    mpz_out_str(stdout, 10, A_size);
    printf(", ");
    mpz_out_str(stdout, 10, AA_size);
    printf("\n");

    mpz_clear(A_size);
    mpz_clear(AA_size);
    return 0;
}
