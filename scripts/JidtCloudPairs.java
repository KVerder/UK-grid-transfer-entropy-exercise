// Independent pair shards; the estimator and per-pair seeds match the local runner.
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class JidtCloudPairs {
  public static void main(String[] args) throws Exception {
    if (args.length != 9) throw new IllegalArgumentException("VALUES OUTPUT N T SHARD SHARDS LIMIT THREADS MINIMUM");
    int n=Integer.parseInt(args[2]), t=Integer.parseInt(args[3]);
    int shard=Integer.parseInt(args[4]), shards=Integer.parseInt(args[5]);
    int limit=Integer.parseInt(args[6]), threads=Integer.parseInt(args[7]), minimum=Integer.parseInt(args[8]);
    if(n<2 || t<3 || shards<1 || shard<0 || shard>=shards || threads<1 || minimum<3 || minimum>t || limit<0)
      throw new IllegalArgumentException("Invalid shard configuration");
    long totalLong=(long)n*(n-1)/2;
    if(totalLong>Integer.MAX_VALUE) throw new IllegalArgumentException("Too many pairs");
    int total=(int)totalLong, available=shard<total ? (total-1-shard)/shards+1 : 0;
    int count=limit==0 ? available : Math.min(limit,available);
    byte[] raw=Files.readAllBytes(Paths.get(args[0]));
    if(raw.length!=(long)n*t*8) throw new IllegalArgumentException("Wrong input size");
    ByteBuffer input=ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
    double[][] data=new double[n][t];
    for(int i=0;i<n;i++)for(int j=0;j<t;j++) {
      data[i][j]=input.getDouble();
      if(Double.isInfinite(data[i][j])) throw new IllegalArgumentException("Infinite input");
    }
    int[] offsets=new int[n], indices=new int[count];
    float[] values=new float[count];
    for(int i=0;i<n;i++) offsets[i]=(int)((long)i*(2L*n-i-1)/2);
    for(int p=0;p<count;p++) {
      // A pilot spans the whole population, not just the first household rows.
      long position=limit==0 ? p : count<2 ? 0 : (long)p*(available-1)/(count-1);
      indices[p]=(int)(shard+position*shards);
    }
    AtomicInteger next=new AtomicInteger();
    ExecutorService pool=Executors.newFixedThreadPool(threads);
    List<Future<?>> futures=new ArrayList<>();
    long started=System.nanoTime();
    try {
      for(int w=0;w<threads;w++)futures.add(pool.submit(() -> {
        try {
          var calculator=JidtKsg.calculator(2);
          double[] x=new double[t], y=new double[t];
          for(int p;(p=next.getAndIncrement())<count;) {
            int index=indices[p], row=Arrays.binarySearch(offsets,index);
            if(row<0)row=-row-2;
            int column=row+1+index-offsets[row], observations=0;
            for(int h=0;h<t;h++)if(Double.isFinite(data[row][h])&&Double.isFinite(data[column][h])) {
              x[observations]=data[row][h]; y[observations++]=data[column][h];
            }
            values[p]=observations<minimum ? Float.NaN : (float)JidtKsg.estimate(calculator,
              Arrays.copyOf(x,observations),Arrays.copyOf(y,observations),42L+index,1e-8);
          }
        } catch(Exception error) { throw new RuntimeException(error); }
      }));
      for(Future<?> future:futures)future.get();
    } finally { pool.shutdownNow(); }
    double seconds=(System.nanoTime()-started)/1e9;
    ByteBuffer output=ByteBuffer.allocate(count*8).order(ByteOrder.LITTLE_ENDIAN);
    for(int p=0;p<count;p++)output.putInt(indices[p]).putFloat(values[p]);
    Files.write(Paths.get(args[1]),output.array());
    System.out.printf(Locale.ROOT,"{\"shard\":%d,\"pairs\":%d,\"seconds\":%.6f,\"available\":%d}%n",shard,count,seconds,available);
  }
}
