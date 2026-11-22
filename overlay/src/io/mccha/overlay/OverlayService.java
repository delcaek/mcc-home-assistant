package io.mccha.overlay;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.drawable.GradientDrawable;
import android.os.IBinder;
import android.os.PowerManager;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import android.os.Handler;
import java.io.FileOutputStream;

public class OverlayService extends Service {
    private WindowManager wm;
    private View overlay;
    private TextView remainTv;
    private final Handler handler = new Handler();
    // the daemon writes the remaining time to files/remaining (seconds, -1 = no timer); read it every 0.5 s
    private final Runnable poll = new Runnable(){ public void run(){
        if (overlay==null) return;
        String t = null;
        try { BufferedReader r = new BufferedReader(new FileReader(new File(getFilesDir(),"remaining")));
              int s = Integer.parseInt(r.readLine().trim()); r.close();
              t = s < 0 ? "no timer" : String.format("%d:%02d left", s/60, s%60); } catch(Exception e){}
        if (t==null) remainTv.setVisibility(View.INVISIBLE);
        else { if (!t.contentEquals(remainTv.getText())) remainTv.setText(t); remainTv.setVisibility(View.VISIBLE); }
        handler.postDelayed(this, 500);
    }};

    @Override public IBinder onBind(Intent i){ return null; }

    @Override public int onStartCommand(Intent intent, int flags, int startId){
        String action = intent==null?null:intent.getStringExtra("action");
        if ("HIDE".equals(action)) { removeOverlay(); stopSelf(); return START_NOT_STICKY; }
        showOverlay();
        return START_STICKY;
    }

    private void showOverlay(){
        if (overlay!=null) return;
        playAlert();
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        DisplayMetrics dm = getResources().getDisplayMetrics();
        int W = dm.widthPixels;

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER);

        RobotView robot = new RobotView(this);
        int rs = (int)(W*0.15f);   // robot size; leaves room for the remaining-time line
        content.addView(robot, new LinearLayout.LayoutParams(rs, rs));

        TextView tv = new TextView(this);
        tv.setText("REMOTE CONTROL ACTIVE");
        tv.setTextColor(Color.WHITE);
        tv.setTypeface(tv.getTypeface(), android.graphics.Typeface.BOLD);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_PX, W*0.05f);
        tv.setLetterSpacing(0.04f);
        tv.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        tlp.topMargin = (int)(W*0.035f);
        content.addView(tv, tlp);

        remainTv = new TextView(this);
        remainTv.setTextColor(0xFFFFD28A);
        remainTv.setTypeface(android.graphics.Typeface.MONOSPACE, android.graphics.Typeface.BOLD);
        remainTv.setTextSize(TypedValue.COMPLEX_UNIT_PX, W*0.05f);
        remainTv.setGravity(Gravity.CENTER);
        remainTv.setVisibility(View.INVISIBLE);
        LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        rlp.topMargin = (int)(W*0.012f);
        content.addView(remainTv, rlp);

        Button b = new Button(this);
        b.setText("STOP");
        b.setTextColor(Color.WHITE);
        b.setTypeface(b.getTypeface(), android.graphics.Typeface.BOLD);
        b.setTextSize(TypedValue.COMPLEX_UNIT_PX, W*0.06f);
        b.setLetterSpacing(0.1f);
        b.setAllCaps(true);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xFFE10600);
        bg.setCornerRadius(W*0.026f);
        b.setBackground(bg);
        b.setPadding((int)(W*0.14f),(int)(W*0.03f),(int)(W*0.14f),(int)(W*0.03f));
        b.setOnClickListener(new View.OnClickListener(){
            public void onClick(View v){
                try { new FileOutputStream(new File(getFilesDir(),"estop")).close(); } catch(Exception e){}
                removeOverlay(); stopSelf();
            }
        });
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        blp.topMargin = (int)(W*0.03f);
        content.addView(b, blp);

        StripeFrame root = new StripeFrame(this);
        root.addView(content, new android.widget.FrameLayout.LayoutParams(
            android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
            android.widget.FrameLayout.LayoutParams.MATCH_PARENT));

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_SYSTEM_ERROR,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
              | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
              | WindowManager.LayoutParams.FLAG_FULLSCREEN
              | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
              | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
              | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
              | WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD,
            PixelFormat.TRANSLUCENT);
        overlay = root;
        try {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            PowerManager.WakeLock wl = pm.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK
                | PowerManager.ACQUIRE_CAUSES_WAKEUP
                | PowerManager.ON_AFTER_RELEASE, "mcc:wake");
            wl.acquire(3000);   // wakes the screen; FLAG_KEEP_SCREEN_ON keeps it on afterwards
        } catch (Exception e) {}
        wm.addView(overlay, lp);
        handler.post(poll);
    }

    private void playAlert(){
        new Thread(new Runnable(){ public void run(){
            try {
                ToneGenerator tg = new ToneGenerator(AudioManager.STREAM_ALARM, 100);
                tg.startTone(ToneGenerator.TONE_PROP_BEEP, 180); Thread.sleep(230);
                tg.startTone(ToneGenerator.TONE_PROP_BEEP2, 320); Thread.sleep(400);
                tg.release();
            } catch (Exception e) {}
        }}).start();
    }

    private void removeOverlay(){
        handler.removeCallbacks(poll);
        if (overlay!=null && wm!=null){ try{ wm.removeView(overlay);}catch(Exception e){} overlay=null; }
    }
    @Override public void onDestroy(){ removeOverlay(); super.onDestroy(); }

    // --- translucent centre (the cooking UI shows through) + opaque red/black striped frame ---
    static class StripeFrame extends android.widget.FrameLayout {
        private final Paint stripe = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint center = new Paint(Paint.ANTI_ALIAS_FLAG);
        StripeFrame(Context c){ super(c);
            setWillNotDraw(false);
            setLayerType(View.LAYER_TYPE_SOFTWARE, null);   // reliable clipPath
            stripe.setStyle(Paint.Style.STROKE); stripe.setColor(0xFFD81B1B);
            center.setStyle(Paint.Style.FILL); center.setColor(0xBF000000); } // ~75 % black
        @Override protected void onDraw(Canvas c){
            int w=getWidth(), h=getHeight();
            float s=w*0.03f, b=w*0.032f, rad=w*0.02f;
            RectF inner=new RectF(b,b,w-b,h-b);
            // centre: translucent
            c.drawRoundRect(inner, rad, rad, center);
            // clip to the frame ring, fill opaque, draw stripes
            c.save();
            Path ring=new Path(); ring.setFillType(Path.FillType.EVEN_ODD);
            ring.addRect(0,0,w,h,Path.Direction.CW);
            ring.addRoundRect(inner, rad, rad, Path.Direction.CW);
            c.clipPath(ring);
            c.drawColor(0xFF000000);
            stripe.setStrokeWidth(s);
            for(float x=-h; x<w+h; x+=s*2) c.drawLine(x,0,x+h,h,stripe);
            c.restore();
        }
    }

    // --- plain white robot icon (Canvas) ---
    static class RobotView extends View {
        private final Paint st = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint fl = new Paint(Paint.ANTI_ALIAS_FLAG);
        RobotView(Context c){ super(c); setWillNotDraw(false);
            st.setColor(Color.WHITE); st.setStyle(Paint.Style.STROKE); st.setStrokeWidth(5);
            st.setStrokeCap(Paint.Cap.ROUND); st.setStrokeJoin(Paint.Join.ROUND);
            fl.setColor(Color.WHITE); fl.setStyle(Paint.Style.FILL); }
        @Override protected void onDraw(Canvas c){
            float s=Math.min(getWidth(),getHeight())/100f;
            c.save();
            c.translate((getWidth()-100*s)/2f,(getHeight()-100*s)/2f);
            c.scale(s,s);
            c.drawLine(50,6,50,16,st); c.drawCircle(50,5,3.5f,fl);
            c.drawRoundRect(new RectF(22,18,78,64),12,12,st);
            c.drawCircle(40,38,6,fl); c.drawCircle(60,38,6,fl);
            Path sm=new Path(); sm.moveTo(38,50); sm.quadTo(50,60,62,50); c.drawPath(sm,st);
            c.drawLine(22,34,15,34,st); c.drawLine(78,34,85,34,st);
            Path bd=new Path(); bd.moveTo(34,64); bd.lineTo(34,72); bd.lineTo(66,72); bd.lineTo(66,64); c.drawPath(bd,st);
            c.restore();
        }
    }
}
