// Resumable MI using the unmodified JIDT KSG algorithm 1 library.
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class JidtPairMI {
    private static final int CHUNK = 2048;
    static void save(Path path, float[] values) throws Exception {
        ByteBuffer buffer = ByteBuffer.allocate(values.length * 4).order(ByteOrder.LITTLE_ENDIAN);
        for (float value : values) buffer.putFloat(value);
        Path temporary = path.resolveSibling(path.getFileName() + ".tmp");
        Files.write(temporary, buffer.array());
        Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING);
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 9) throw new IllegalArgumentException("WORK N T MIN_OVERLAP K THREADS SEED NOISE CHECKPOINT_DIR");
        Path work = Paths.get(args[0]), checkpoint = Paths.get(args[8]);
        int houses = Integer.parseInt(args[1]), times = Integer.parseInt(args[2]);
        int minimum = Integer.parseInt(args[3]), k = Integer.parseInt(args[4]), threads = Integer.parseInt(args[5]);
        long seed = Long.parseLong(args[6]);
        double noise = Double.parseDouble(args[7]);
        long pairCount = (long) houses * (houses - 1) / 2;
        if (houses < 2 || times < 2 || times > 65535 || minimum <= k || minimum > times ||
            k < 1 || threads < 1 || noise < 0 || !Double.isFinite(noise) || pairCount > Integer.MAX_VALUE)
            throw new IllegalArgumentException("Invalid dimensions or settings");
        byte[] bytes = Files.readAllBytes(work.resolve("values.bin"));
        if (bytes.length != (long) houses * times * 8) throw new IllegalArgumentException("Wrong values byte length");
        ByteBuffer input = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        double[][] data = new double[houses][times];
        for (int i=0; i<houses; i++) for (int t=0; t<times; t++) {
            data[i][t] = input.getDouble();
            if (Double.isInfinite(data[i][t])) throw new IllegalArgumentException("Infinite reading");
        }
        float[] result = new float[(int)pairCount]; Arrays.fill(result, Float.NaN);
        int[] offsets = new int[houses];
        for (int i=0; i<houses; i++) offsets[i] = (int)((long)i * (2L*houses-i-1)/2);
        Files.createDirectories(checkpoint);
        int chunks = ((int)pairCount + CHUNK - 1) / CHUNK;
        AtomicInteger nextChunk = new AtomicInteger(), complete = new AtomicInteger(), reused = new AtomicInteger();
        AtomicLong nextReport = new AtomicLong(System.currentTimeMillis()+10000);
        long started = System.nanoTime();
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        List<Future<?>> futures = new ArrayList<>();
        try {
            for (int worker=0; worker<threads; worker++) futures.add(pool.submit(() -> {
                try {
                    var calculator = JidtKsg.calculator(k);
                    double[] x = new double[times], y = new double[times];
                    for (int chunk; (chunk=nextChunk.getAndIncrement())<chunks;) {
                        int begin=chunk*CHUNK, end=Math.min((int)pairCount,begin+CHUNK);
                        Path file=checkpoint.resolve(String.format(Locale.ROOT,"chunk-%06d.bin",chunk));
                        float[] values=new float[end-begin];
                        if (Files.exists(file)) {
                            byte[] cached=Files.readAllBytes(file);
                            if(cached.length != values.length*4) throw new IllegalStateException("Damaged checkpoint: "+file);
                            ByteBuffer saved=ByteBuffer.wrap(cached).order(ByteOrder.LITTLE_ENDIAN);
                            for(int p=0;p<values.length;p++) values[p]=saved.getFloat();
                            reused.addAndGet(values.length);
                        } else {
                            for(int index=begin;index<end;index++) {
                                int row=Arrays.binarySearch(offsets,index);
                                if(row<0)row=-row-2;
                                int column=row+1+index-offsets[row], count=0;
                                for(int t=0;t<times;t++)if(Double.isFinite(data[row][t])&&Double.isFinite(data[column][t])) {
                                    x[count]=data[row][t];y[count++]=data[column][t];
                                }
                                values[index-begin]=count<minimum ? Float.NaN :
                                    (float)JidtKsg.estimate(calculator,Arrays.copyOf(x,count),Arrays.copyOf(y,count),seed+index,noise);
                            }
                            save(file,values);
                        }
                        System.arraycopy(values,0,result,begin,values.length);
                        int done=complete.addAndGet(values.length);
                        long now=System.currentTimeMillis(),reportAt=nextReport.get();
                        if(now>=reportAt && nextReport.compareAndSet(reportAt,now+10000)) {
                            double seconds=(System.nanoTime()-started)/1e9;
                            System.out.printf(Locale.ROOT,"KSG-1 checkpointed %,d / %,d pairs; resumed %,d; elapsed %.1fs%n",done,pairCount,reused.get(),seconds);
                        }
                    }
                } catch(Exception failure){throw new RuntimeException(failure);}
            }));
            for(Future<?> future:futures)future.get();
        } finally {pool.shutdownNow();}
        save(work.resolve("mutual_information.bin"),result);
        System.out.println("JIDT KSG-1 completed "+pairCount+" pair slots; output in nats");
    }
}
