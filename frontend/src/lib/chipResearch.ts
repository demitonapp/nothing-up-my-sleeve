// The chips: what the research says about the hardware models are trained on (13 November, Justin: "a card here
// ... that focuses purely on chips then when clicking it's a page with 5 tabs for chip kinds, time to train, trend
// lines, bottlenecks, source of leaps with the latest information and a summary of all of them").
//
// Gathered 13 November 2026 from the sources each tab cites. Vendor figures are marked as vendor figures; MLPerf
// rounds are read from the vendors' and the press's reports of them, not from MLCommons' own tables. Our own
// readings (the M6 mini against the rented RTX 4090) are the ledger's, measured 11 and 12 November.
// Drawn by components/Chips.tsx at /orbitals/demiton/discoveries/chips/<tab>.

export const CHIP_TABS = [
  { key: 'kinds', label: 'Chip kinds' },
  { key: 'time-to-train', label: 'Time to train' },
  { key: 'trends', label: 'Trend lines' },
  { key: 'bottlenecks', label: 'Bottlenecks' },
  { key: 'leaps', label: 'Source of leaps' },
] as const;
export type ChipTab = (typeof CHIP_TABS)[number]['key'];
export const CHIP_PATHS = ['chips', ...CHIP_TABS.map((t) => `chips/${t.key}`)];
export const isChipTab = (s: string | null | undefined): s is ChipTab => CHIP_TABS.some((t) => t.key === s);

export const GATHERED = '13 November 2026';

export interface Source { label: string; href: string }

const S = {
  mlperf6: { label: 'NVIDIA on MLPerf Training v6.0 (June 2026)', href: 'https://developer.nvidia.com/blog/nvidia-blackwell-tops-mlperf-training-6-0-with-industry-leading-scale-and-performance/' },
  mlperf6buyers: { label: 'MLPerf Training v6.0 for GPU buyers (Spheron)', href: 'https://www.spheron.network/blog/mlperf-training-v6-0-results-what-they-mean-for-gpu-buyers-2/' },
  mlperf6table: { label: 'MLPerf Training v6.0: NVIDIA ran the table', href: 'https://news.whatthechiphappened.com/p/mlperf-training-v60-nvidia-ran-the' },
  mlperf51: { label: 'NVIDIA wins every MLPerf Training v5.1 benchmark (Nov 2025)', href: 'https://blogs.nvidia.com/blog/mlperf-training-benchmark-blackwell-ultra/' },
  apple: { label: 'Feng et al., Profiling Apple Silicon Performance for ML Training (2025)', href: 'https://arxiv.org/abs/2501.14925' },
  mlxTs: { label: 'PyTorch vs MLX on Apple silicon, transformer time-series models (2025)', href: 'https://www.researchgate.net/publication/408288681_Benchmarking_transformer-based_time_series_models_pytorch_vs_mlx_on_apple_silicon' },
  m5: { label: 'Apple, Exploring LLMs with MLX and the M5 Neural Accelerators', href: 'https://machinelearning.apple.com/research/exploring-llms-mlx-m5' },
  laics: { label: 'Reuther et al., Lincoln AI Computing Survey (LAICS) and Trends (MIT, Oct 2025)', href: 'https://arxiv.org/abs/2510.20931' },
  epochHw: { label: 'Epoch AI, Trends in machine learning hardware', href: 'https://epoch.ai/blog/trends-in-machine-learning-hardware' },
  epochGpu: { label: 'Epoch AI, Trends in GPU price-performance (2022)', href: 'https://epoch.ai/blog/trends-in-gpu-price-performance' },
  epochData: { label: 'Epoch AI, Machine learning hardware data', href: 'https://epoch.ai/data/machine-learning-hardware' },
  memwall: { label: 'Gholami et al., AI and Memory Wall (IEEE Micro, 2024)', href: 'https://arxiv.org/abs/2403.14123' },
  algo: { label: 'Ho et al., Algorithmic progress in language models (Epoch, 2024)', href: 'https://epoch.ai/blog/algorithmic-progress-in-language-models' },
  origin: { label: 'Gundlach et al., On the Origin of Algorithmic Progress in AI (MIT, 2025)', href: 'https://arxiv.org/abs/2511.21622' },
  lottery: { label: 'Hooker, The Hardware Lottery (2020)', href: 'https://arxiv.org/abs/2009.06489' },
  ironwood: { label: 'The Register on Google’s Ironwood TPU (Apr 2025)', href: 'https://www.theregister.com/2025/04/10/googles_7thgen_ironwood_tpus_debut/' },
  semi: { label: 'SemiAnalysis, TPU InferenceX', href: 'https://newsletter.semianalysis.com/p/tpu-inferencex-full-steam' },
  cerebras: { label: 'Cerebras CS-3 / WSE-3 launch (Mar 2024)', href: 'https://www.businesswire.com/news/home/20240313320383/en' },
  beyond: { label: 'Introl, AI accelerators beyond GPUs', href: 'https://introl.com/blog/ai-accelerators-beyond-gpus-tpu-trainium-gaudi-cerebras' },
} satisfies Record<string, Source>;

/** The summary over all five tabs: one line a tab, then what it means for this fleet. */
export const SUMMARY: { tab: ChipTab; line: string }[] = [
  { tab: 'kinds', line: 'Six kinds of chip train models today, but almost all large training runs on two: NVIDIA and AMD GPUs, and the tensor chips the clouds build for themselves (Google’s TPU, Amazon’s Trainium). Wafer-scale, unified-memory (Apple) and experimental kinds are niches for training.' },
  { tab: 'time-to-train', line: 'NVIDIA leads every measured training test and is the only vendor that enters them all (MLPerf v6.0, June 2026). AMD is within 5 to 6% of a B200 on the few tests it enters. Google and Amazon mostly do not publish training results, so their standing is a claim, not a measurement.' },
  { tab: 'trends', line: 'Underneath the launch headlines the trend is steady: arithmetic per dollar doubles about every 2.1 years, per watt about every 3 years, while memory capacity and bandwidth double only every 4.' },
  { tab: 'bottlenecks', line: 'Memory, not arithmetic, is the wall: peak arithmetic grows about 3x every two years, memory bandwidth 1.6x, links between chips 1.4x. On Apple the gap to NVIDIA is mostly software (half-precision maths routines), not the silicon.' },
  { tab: 'leaps', line: 'The big jumps in results come from more compute and better methods, not from one chip. Better methods cut the compute needed for the same loss about 3x a year, but much of that was the single move to transformers, and it pays far less at small sizes.' },
];

export const FOR_US = [
  'Almost every figure here is measured on large models across thousands of chips. At our sizes the ranking can flip: the rented RTX 4090 ran a 300k at 0.46x the speed of the M6 mini and a 9m at only 1.07x (our ledger, 12 November). That is why only 9m and up are sent abroad.',
  'On the M6 a step’s time follows the attention maps (layers x heads), not the parameter count, and evaluations took 20 to 25% of a small voyage’s wall time (our ledger, 11 November). The cheap wins are ours to make in software, as the Apple paper finds.',
  'The $100 bet’s 350m is the first size where the research applies directly: one rented H100 for about 9 hours, cheaper than any machine we could buy for it (the hardware ROI study, 7 November).',
];

// ---------------------------------------------------------------- chip kinds

export interface ChipKind { kind: string; examples: string; how: string; strong: string; weak: string; trains: string }
export const KINDS: ChipKind[] = [
  {
    kind: 'General-purpose GPU',
    examples: 'NVIDIA Blackwell (B200, GB300), Hopper (H100); AMD Instinct MI355X',
    how: 'Thousands of small cores plus dedicated matrix units (tensor cores), fed by stacked high-bandwidth memory (HBM) beside the chip.',
    strong: 'Runs any model; the most mature software (CUDA, and AMD’s ROCm catching up); sold by everyone, rented everywhere.',
    weak: 'Power and price; memory per chip lags the models; NVIDIA’s lead is as much its software as its silicon.',
    trains: 'Almost all frontier training',
  },
  {
    kind: 'Tensor chip (cloud ASIC)',
    examples: 'Google TPU v7 Ironwood; AWS Trainium3; Intel Gaudi 3',
    how: 'A grid of multiply-add units built only for matrix maths (a systolic array), many chips wired into one pod: Ironwood pods hold 9,216 chips, each 4.6 PFLOP/s FP8 with 192 GB of HBM (Google’s figures).',
    strong: 'Price per sum at scale inside its own cloud; huge pods with fast links; Google trains Gemini on them.',
    weak: 'Only in one cloud; software tied to JAX/XLA or Amazon’s Neuron; Ironwood is built for serving first, with no native FP4.',
    trains: 'Large training inside Google and Amazon',
  },
  {
    kind: 'Wafer-scale',
    examples: 'Cerebras WSE-3 (CS-3)',
    how: 'One chip the size of a whole silicon wafer: 900,000 cores and 44 GB of fast on-chip memory, rated 125 PFLOP/s peak (Cerebras’ figures).',
    strong: 'No slow trip to outside memory for what fits on the wafer; a large model need not be split across chips by hand.',
    weak: 'Few independent training results; for ordinary dense transformers NVIDIA stays competitive; now sold mostly for fast serving.',
    trains: 'Niche training, mostly serving',
  },
  {
    kind: 'Unified-memory desktop chip',
    examples: 'Apple M-series (this Mac: M6 mini); NVIDIA DGX Spark (GB10); AMD Strix Halo',
    how: 'The processor and the GPU share one pool of ordinary memory, so a model can use most of the machine’s memory without copying.',
    strong: 'Much memory per dollar, low power, silent; similar energy per training step to an RTX 4090 (Feng et al.).',
    weak: 'Low memory bandwidth and slower matrix maths: about 3 to 4x slower than an NVIDIA card of the same price (M2 chips, 2025); young software (MLX).',
    trains: 'Small models, fine-tuning, research (us)',
  },
  {
    kind: 'Dataflow and reconfigurable',
    examples: 'SambaNova; Tenstorrent; Groq LPU (serving only)',
    how: 'The model is laid out across the chip as a pipeline the data flows through, rather than fetched instruction by instruction (Lincoln calls these CGRAs and microcore meshes).',
    strong: 'Very fast and steady serving; less time lost moving data.',
    weak: 'Small software ecosystems; little published training at language-model scale.',
    trains: 'Rarely; mostly serving',
  },
  {
    kind: 'Beyond ordinary silicon',
    examples: 'Optical (Q.ANT’s accelerator, 2025); analog in-memory and memristors; neuromorphic; cryogenic',
    how: 'Doing the sums with light, with the physics of memory cells, or with spiking circuits instead of digital logic.',
    strong: 'Promise of far lower energy per sum.',
    weak: 'Research or first products; low precision and no training of language models at any useful scale yet.',
    trains: 'Not yet',
  },
];

/** How the Lincoln survey sorts them: its axes, each in plain words. */
export const LAICS_AXES: { axis: string; values: string }[] = [
  { axis: 'Power class', values: 'very low power, embedded, autonomous (cars, drones), data-centre chips and cards, data-centre systems' },
  { axis: 'Form', values: 'a chip, a card, or a whole system' },
  { axis: 'Training or not', values: 'inference only, or training and inference' },
  { axis: 'Number precision', values: 'the size of the numbers it does sums in: int8, fp16/bf16 (the training default), fp8 and fp4 (the new gains)' },
  { axis: 'Architecture', values: 'from most flexible to most fixed: CPU, vector engine, GPU, tensor array, microcore mesh, CGRA, FPGA, ASIC' },
  { axis: 'Technology', values: 'ordinary digital silicon, or the non-CMOS kinds: memristor, neuromorphic, cryogenic, optical' },
];

// ---------------------------------------------------------------- time to train

export interface Round { round: string; when: string; facts: string[] }
export const ROUNDS: Round[] = [
  {
    round: 'MLPerf Training v6.0', when: 'June 2026',
    facts: [
      '95 systems from 24 organisations.',
      'NVIDIA entered every test and won each at scale; it appears on about 197 of the round’s 227 results.',
      'New tests for mixture-of-experts models (DeepSeek-V3 671B, GPT-OSS-20B); NVIDIA’s GB300 NVL72 set the records, up to 8,192 GPUs.',
      'Llama 3.1 405B pre-training in 7.07 minutes at NVIDIA’s largest scale; GB300 up to 1.6x faster than GB200 at the same scale.',
      'AMD’s MI355X within 5% of the B200 on Llama 2 70B fine-tuning and 6% on Llama 3.1 8B pre-training (AMD’s figures, both FP4); AMD’s first multi-machine entry (64 MI325X).',
      'No confirmed Google TPU or Amazon Trainium entry.',
    ],
  },
  {
    round: 'MLPerf Training v5.1', when: 'November 2025',
    facts: [
      'GB300 NVL72 more than 4x Hopper on Llama 3.1 405B pre-training, and nearly 5x on Llama 2 70B fine-tuning, with the same number of GPUs (NVIDIA’s figures).',
      'Llama 3.1 405B in 10 minutes on more than 5,000 Blackwell GPUs, 2.7x the previous round’s best, mostly from more GPUs and the first use of 4-bit numbers (NVFP4) in training.',
      'At 512 GPUs, GB300 trained 405B 1.9x faster than GB200 had the round before.',
    ],
  },
];

export const READ_MLPERF: string[] = [
  'What it measures: the wall-clock time for a set model to reach a set quality, on systems the vendors submit and their rivals review.',
  'Who is absent matters: a vendor enters only the tests it chooses, so a missing result is not a loss, but it is not a measurement either.',
  'A record at 5,000 GPUs says how well a vendor’s links and software scale, not how fast one chip is. Compare at the same GPU count.',
  'Number size is not held equal: a 4-bit result beside an 8-bit one is partly a precision gain, not a chip gain.',
  'Serving (inference) comparisons are not training ones. SemiAnalysis puts Ironwood’s serving cost below a B200’s ($0.18 against $0.22 per million tokens, modelled), but there is no independent training comparison of the two.',
];

// ---------------------------------------------------------------- trend lines

export interface Trend { what: string; doubles: string; tenfold?: string; note: string; src: Source }
export const TRENDS: Trend[] = [
  { what: 'Arithmetic per dollar (ML GPUs)', doubles: '2.1 years', tenfold: '7 years', note: '47 ML accelerators, 2010 to 2023, FP32', src: S.epochHw },
  { what: 'Arithmetic per dollar (all GPUs)', doubles: '2.5 years', note: '470 GPUs; ML-research GPUs alone 2.1 years, the fastest GPU of each year 3.0 years', src: S.epochGpu },
  { what: 'Peak arithmetic per chip (ML)', doubles: '2.3 years', note: 'peak FLOP/s on the spec sheet', src: S.epochHw },
  { what: 'Arithmetic per watt (ML GPUs)', doubles: '3.0 years', note: 'all ML GPUs; general GPUs 2.7 years', src: S.epochHw },
  { what: 'Arithmetic per watt (leading GPUs and TPUs)', doubles: '1.7 years', note: 'about 50% more efficient each year at the top', src: S.epochData },
  { what: 'Memory capacity per chip', doubles: '4 years', note: 'half the pace of arithmetic', src: S.epochHw },
  { what: 'Memory bandwidth per chip', doubles: '4.1 years', note: 'the trend behind the memory wall', src: S.epochHw },
  { what: 'Moore’s law, for comparison', doubles: '2 years', note: 'transistors per chip', src: S.epochGpu },
];

/** The other lever on the trend line: smaller numbers. */
export const PRECISION: { format: string; gain: string }[] = [
  { format: 'FP32 (no matrix units)', gain: '1x, the baseline' },
  { format: 'TF32 on matrix units', gain: 'about 3x' },
  { format: 'FP16 / BF16 on matrix units (the training default)', gain: 'about 8x' },
  { format: 'INT8 on matrix units', gain: 'about 14x' },
  { format: 'FP8, then FP4 (Blackwell’s NVFP4)', gain: 'each halving roughly doubles the sums again; FP4 entered MLPerf training in v5.1' },
];

export const TREND_NOTES: string[] = [
  'These are spec-sheet peaks. Real training uses a fraction of them, and the fraction depends more on software and memory than on the peak.',
  'The trend is smooth over a decade; a single launch can still look like a leap, because each new generation also moves to smaller numbers and bigger systems at once.',
  'Our own trend line is the M6 mini’s step-time law: about 12.5 ms for each layer-times-head, plus about 22 ms per pinned head (our ledger, 11 November).',
];

// ---------------------------------------------------------------- bottlenecks

export interface Wall { wall: string; finding: string; numbers: string; src: Source | null }
export const WALLS: Wall[] = [
  {
    wall: 'Memory bandwidth (the memory wall)',
    finding: 'Chips can do sums far faster than they can be fed. Decoder models like ours are hit hardest, because each step reads a lot and computes little.',
    numbers: 'Peak arithmetic 3.0x every two years; memory bandwidth 1.6x; links between chips 1.4x. Large-model parameters grew 410x every two years while a GPU’s memory grew 2x.',
    src: S.memwall,
  },
  {
    wall: 'Memory capacity',
    finding: 'When a model and its training state do not fit on one chip, it must be split, and the splitting costs time. The Apple paper found an M2 Ultra beating an RTX 4090 once the 4090 ran out of memory and had to offload.',
    numbers: 'Capacity per chip doubles every 4 years; Ironwood holds 192 GB, a B200 192 GB, an M-series Mac up to its whole memory.',
    src: S.apple,
  },
  {
    wall: 'Software and kernels',
    finding: 'On Apple the main gap to NVIDIA is the half-precision maths routines, then memory that creeps up, page faults and slow kernel launches. The same chip runs 1.02 to 3.12x faster under MLX than under PyTorch.',
    numbers: 'Apple about 3 to 4x slower than a same-price NVIDIA card (M2 chips); MLX 1.02 to 3.12x faster than PyTorch MPS (M4 Pro).',
    src: S.apple,
  },
  {
    wall: 'Attention’s memory',
    finding: 'A window’s cost is in holding the attention map. Computing it in tiles that fit the chip’s fast memory (IO-aware attention) is several times faster and exact.',
    numbers: 'Our own step-time law agrees: layers x heads, not parameters, set the M6’s step.',
    src: { label: 'The field: IO-aware attention (Dao et al.), under architecture', href: '/orbitals/demiton/discoveries/object-of-study/architecture' },
  },
  {
    wall: 'Precision support',
    finding: 'A chip without matrix units for small numbers loses most of the gain from them: Apple’s M2 gained almost nothing from FP16 where NVIDIA’s tensor cores doubled. Ironwood has no native FP4, so it is compared at FP8.',
    numbers: 'On this Mac bf16 is fastest; float16 runs at 0.72x and float32 at 0.51x (our ledger).',
    src: S.apple,
  },
  {
    wall: 'Links between chips',
    finding: 'At thousands of chips, training waits on the network. MLPerf records at 5,000 to 8,000 GPUs are mostly records for NVIDIA’s links (NVLink, 72 GPUs to a rack) and software.',
    numbers: 'Interconnect bandwidth 1.4x every two years, the slowest of the three.',
    src: S.memwall,
  },
];

// ---------------------------------------------------------------- source of leaps

export interface Leap { leap: string; size: string; drove: string; src: Source }
export const LEAPS: Leap[] = [
  { leap: 'Better methods, for the same loss', size: 'about 3x less compute a year (halving every 8 months or so)', drove: 'Architectures, training recipes and data; worth roughly half as much as the growth in compute itself', src: S.algo },
  { leap: 'The switch to transformers', size: 'most of the measured methods gain', drove: 'A change whose pay-off grows with scale: large at frontier size, much smaller for small models', src: S.origin },
  { leap: 'Hopper to Blackwell Ultra', size: 'more than 4x on Llama 3.1 405B at the same GPU count', drove: 'A new chip and 4-bit numbers and a 72-GPU rack, all at once (NVIDIA’s figures)', src: S.mlperf51 },
  { leap: 'GB200 to GB300', size: '1.6 to 1.9x at the same scale', drove: 'One generation step: more memory, faster small-number units', src: S.mlperf6 },
  { leap: 'M4 to M5 (Apple)', size: 'up to 4x on matrix-heavy work; 19 to 27% on token generation', drove: 'New matrix units in the GPU; the smaller gain tracks memory bandwidth (120 to 153 GB/s). Serving figures; no training figure published', src: S.m5 },
  { leap: 'The chip trend itself', size: '2x arithmetic per dollar every 2.1 years', drove: 'Smaller transistors, matrix units and smaller numbers', src: S.epochHw },
];

export const LEAP_NOTES: { title: string; body: string; src: Source }[] = [
  {
    title: 'The hardware lottery',
    body: 'An idea wins partly because it suits the chips of its day, not only because it is better. Transformers won on GPUs because they are mostly large matrix sums; ideas that need other shapes of computation lose before they are tried at scale.',
    src: S.lottery,
  },
  {
    title: 'Methods gains are contested at small sizes',
    body: 'The MIT study finds methods progress for small models far slower than the headline 3x a year, and that how big the gain looks depends on which old model it is measured against. Our ships are small, so the honest expectation is that most of our gains will come from what we teach and measure, not from borrowed recipes or faster chips.',
    src: S.origin,
  },
  {
    title: 'Compute is still the bigger lever',
    body: 'Across 200 language-model results, more compute explains about twice as much of the gain as better methods. A chip matters through how much compute a dollar buys, which is why renting the newest chip by the hour usually beats owning an older one.',
    src: S.algo,
  },
];

export const TAB_SOURCES: Record<ChipTab, Source[]> = {
  kinds: [S.laics, S.ironwood, S.cerebras, S.apple, S.beyond],
  'time-to-train': [S.mlperf6, S.mlperf6buyers, S.mlperf6table, S.mlperf51, S.semi],
  trends: [S.epochHw, S.epochGpu, S.epochData],
  bottlenecks: [S.memwall, S.apple, S.mlxTs],
  leaps: [S.algo, S.origin, S.lottery, S.mlperf51, S.mlperf6, S.m5],
};
