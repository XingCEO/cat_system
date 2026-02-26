import{j as t,i as Ke,u as He}from"./vendor-data-BGC679gK.js";import{r as l}from"./vendor-react-CfDhA8Yr.js";import{a as Ve,P as qe,C as pe,b as Oe,T as xe,O as ge,D as he,c as Je,V as Xe,d as ve,I as Ye,e as Ge,f as be,g as Qe,h as ye,i as Ze,j as De,k as we,l as je,L as Ne,m as ke}from"./vendor-radix-DB-zNCEb.js";import{c as v,B as E}from"./index-eZrj1bNV.js";import{X as et,v as Se,w as tt,x as st,y as at,z as it,E as nt,G as fe,T as ot,H as rt,I as lt,L as ct,J as dt,l as mt}from"./vendor-utils-Duyaqd-6.js";import{a as ut}from"./InteractiveChartContainer--47WPMjx.js";import"./vendor-charts-D18Uve9I.js";function Tt(e,a=2){return e==null?"-":`${e>=0?"+":""}${e.toFixed(a)}%`}function Ft(e){return e==null?"-":e.toLocaleString("zh-TW")}function Ut(e){return e==null?"-":e.toFixed(2)}function zt(e){return e==null?"text-muted-foreground":e>0?"text-red-500":e<0?"text-green-500":"text-muted-foreground"}const ft=Ve,pt=qe,$e=l.forwardRef(({className:e,...a},s)=>t.jsx(ge,{ref:s,className:v("fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",e),...a}));$e.displayName=ge.displayName;const _e=l.forwardRef(({className:e,children:a,...s},n)=>t.jsxs(pt,{children:[t.jsx($e,{}),t.jsxs(pe,{ref:n,className:v("fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-2xl duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-xl focus:outline-none",e),...s,children:[a,t.jsxs(Oe,{className:"absolute right-3 top-3 z-20 rounded-full p-1.5 bg-muted/80 text-muted-foreground transition-all duration-200 hover:bg-destructive/10 hover:text-destructive focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none",children:[t.jsx(et,{className:"h-4 w-4"}),t.jsx("span",{className:"sr-only",children:"關閉"})]})]})]}));_e.displayName=pe.displayName;const Ce=({className:e,...a})=>t.jsx("div",{className:v("flex flex-col space-y-1.5 text-center sm:text-left",e),...a});Ce.displayName="DialogHeader";const Re=l.forwardRef(({className:e,...a},s)=>t.jsx(xe,{ref:s,className:v("text-lg font-semibold leading-none tracking-tight",e),...a}));Re.displayName=xe.displayName;const xt=l.forwardRef(({className:e,...a},s)=>t.jsx(he,{ref:s,className:v("text-sm text-muted-foreground",e),...a}));xt.displayName=he.displayName;const gt=Je,ht=Xe,Le=l.forwardRef(({className:e,children:a,...s},n)=>t.jsxs(ve,{ref:n,className:v("flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1",e),...s,children:[a,t.jsx(Ye,{asChild:!0,children:t.jsx(Se,{className:"h-4 w-4 opacity-50"})})]}));Le.displayName=ve.displayName;const Te=l.forwardRef(({className:e,...a},s)=>t.jsx(we,{ref:s,className:v("flex cursor-default items-center justify-center py-1",e),...a,children:t.jsx(st,{className:"h-4 w-4"})}));Te.displayName=we.displayName;const Fe=l.forwardRef(({className:e,...a},s)=>t.jsx(je,{ref:s,className:v("flex cursor-default items-center justify-center py-1",e),...a,children:t.jsx(Se,{className:"h-4 w-4"})}));Fe.displayName=je.displayName;const Ue=l.forwardRef(({className:e,children:a,position:s="popper",...n},i)=>t.jsx(Ge,{children:t.jsxs(be,{ref:i,className:v("relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",s==="popper"&&"data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1",e),position:s,...n,children:[t.jsx(Te,{}),t.jsx(Qe,{className:v("p-1",s==="popper"&&"h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]"),children:a}),t.jsx(Fe,{})]})}));Ue.displayName=be.displayName;const vt=l.forwardRef(({className:e,...a},s)=>t.jsx(Ne,{ref:s,className:v("py-1.5 pl-8 pr-2 text-sm font-semibold",e),...a}));vt.displayName=Ne.displayName;const ze=l.forwardRef(({className:e,children:a,...s},n)=>t.jsxs(ye,{ref:n,className:v("relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",e),...s,children:[t.jsx("span",{className:"absolute left-2 flex h-3.5 w-3.5 items-center justify-center",children:t.jsx(Ze,{children:t.jsx(tt,{className:"h-4 w-4"})})}),t.jsx(De,{children:a})]}));ze.displayName=ye.displayName;const bt=l.forwardRef(({className:e,...a},s)=>t.jsx(ke,{ref:s,className:v("-mx-1 my-1 h-px bg-muted",e),...a}));bt.displayName=ke.displayName;const x=Ke.create({baseURL:"/api",timeout:12e4});x.interceptors.response.use(e=>e,e=>{var s,n,i,c,f,w,g;const a=((n=(s=e.response)==null?void 0:s.data)==null?void 0:n.detail)||((c=(i=e.response)==null?void 0:i.data)==null?void 0:c.error)||e.message||"請求失敗，請稍後再試";return e.code==="ECONNABORTED"?console.error("API 請求超時:",(f=e.config)==null?void 0:f.url):((w=e.response)==null?void 0:w.status)===400?console.warn("API 請求參數錯誤:",a):((g=e.response)==null?void 0:g.status)>=500&&console.error("伺服器錯誤:",a),Promise.reject(new Error(a))});async function Pt(e){const a=new URLSearchParams;Object.entries(e).forEach(([n,i])=>{i!=null&&(Array.isArray(i)?a.set(n,i.join(",")):a.set(n,String(i)))});const{data:s}=await x.get(`/stocks/filter?${a}`);return s.data}async function At(){const{data:e}=await x.get("/trading-date");return e.data}async function It(e,a){const s=new URLSearchParams;e&&s.set("date",e);const{data:n}=await x.get(`/turnover/limit-up?${s}`);return n}async function Et(e){const a=e?`?date=${e}`:"",{data:s}=await x.get(`/turnover/top20${a}`);return s}async function Mt(e){const a=e?`?date=${e}`:"",{data:s}=await x.get(`/turnover/top20-limit-up${a}`);return s}async function Wt(e,a){const s=new URLSearchParams;e&&s.set("start_date",e),a&&s.set("end_date",a);const{data:n}=await x.get(`/turnover/top200-limit-up?${s}`);return n}async function Bt(e,a,s,n){const i=new URLSearchParams;e&&i.set("start_date",e),a&&i.set("end_date",a),s!==void 0&&i.set("change_min",String(s)),n!==void 0&&i.set("change_max",String(n));const{data:c}=await x.get(`/turnover/top200-change-range?${i}`);return c}async function Kt(e,a){const s=new URLSearchParams;e&&s.set("start_date",e),a&&s.set("end_date",a);const{data:n}=await x.get(`/turnover/top200-5day-high?${s}`);return n}async function Ht(e,a){const s=new URLSearchParams;e&&s.set("start_date",e),a&&s.set("end_date",a);const{data:n}=await x.get(`/turnover/top200-5day-low?${s}`);return n}async function Vt(e,a,s,n){const i=new URLSearchParams;e&&i.set("start_date",e),a&&i.set("end_date",a),s!==void 0&&i.set("min_change",String(s)),n!==void 0&&i.set("max_change",String(n));const{data:c}=await x.get(`/turnover/ma-breakout?${i}`);return c}async function qt(e,a,s){const n=new URLSearchParams;e&&n.set("start_date",e),a&&n.set("end_date",a),s!==void 0&&n.set("volume_ratio",String(s));const{data:i}=await x.get(`/turnover/volume-surge?${n}`);return i}async function Ot(e,a,s){const n=new URLSearchParams;e&&n.set("start_date",e),a&&n.set("end_date",a),s!==void 0&&n.set("min_days",String(s));const{data:i}=await x.get(`/turnover/institutional-buy?${n}`);return i}async function Jt(e,a,s,n,i,c,f,w,g,k){const d=new URLSearchParams;e&&d.set("start_date",e),a&&d.set("end_date",a),s!==void 0&&d.set("turnover_min",String(s)),n!==void 0&&d.set("turnover_max",String(n)),i!==void 0&&d.set("change_min",String(i)),c!==void 0&&d.set("change_max",String(c)),f!==void 0&&d.set("min_buy_days",String(f)),w!==void 0&&d.set("volume_ratio",String(w)),g!==void 0&&d.set("is_5day_high",String(g)),k!==void 0&&d.set("is_5day_low",String(k));const{data:b}=await x.get(`/turnover/combo-filter?${d}`);return b}function Xt(e,a,s){let n,i,c;if(e==="csv"){const k=Object.keys(a[0]||{}).join(","),d=a.map(b=>Object.values(b).map(U=>`"${U}"`).join(","));n=[k,...d].join(`
`),i="text/csv",c="csv"}else if(e==="json")n=JSON.stringify(a,null,2),i="application/json",c="json";else{const k=Object.keys(a[0]||{}),d=h=>String(h??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"),b=k.map(h=>`<Cell><Data ss:Type="String">${d(h)}</Data></Cell>`).join(""),U=a.map(h=>"<Row>"+k.map(L=>{const p=h[L];return`<Cell><Data ss:Type="${typeof p=="number"&&isFinite(p)?"Number":"String"}">${d(p)}</Data></Cell>`}).join("")+"</Row>").join(`
`);n=`<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Worksheet ss:Name="Sheet1"><Table>
<Row>${b}</Row>
${U}
</Table></Worksheet></Workbook>`,i="application/vnd.ms-excel",c="xls"}const f=new Blob(["\uFEFF"+n],{type:`${i};charset=utf-8`}),w=URL.createObjectURL(f),g=document.createElement("a");g.href=w,g.download=`${s}.${c}`,document.body.appendChild(g),g.click(),document.body.removeChild(g),URL.revokeObjectURL(w)}async function yt(e,a="day",s=5,n=!1){let i,c;typeof e=="string"?(c=e,i=new URLSearchParams,i.set("period",a),i.set("years",s.toString()),n&&i.set("force_refresh","true")):(c=e.symbol,i=new URLSearchParams,i.set("period",e.period||"day"),e.startDate&&i.set("start_date",e.startDate),e.endDate&&i.set("end_date",e.endDate),!e.startDate&&!e.endDate&&i.set("years",(e.years||5).toString()),e.forceRefresh&&i.set("force_refresh","true"));const{data:f}=await x.get(`/stocks/${c}/kline?${i}`);return f.data}function O(e){return e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;")}const wt=[{value:"day",label:"日K"},{value:"week",label:"週K"},{value:"month",label:"月K"}],jt={normal:{main:350,volume:100,indicator:180,dialogWidth:"max-w-5xl"},large:{main:500,volume:130,indicator:220,dialogWidth:"max-w-6xl"},xlarge:{main:650,volume:160,indicator:280,dialogWidth:"max-w-[95vw]"}},Nt=5;function Yt({open:e,onClose:a,symbol:s,name:n}){var ie,ne,oe,re;const[i,c]=l.useState("day"),[f,w]=l.useState(!1),[g]=l.useState("xlarge"),[k,d]=l.useState(0),[b,U]=l.useState(null),[h,L]=l.useState(null),[p,z]=l.useState(!1),J=l.useRef(null),Pe=l.useCallback(o=>{p||U(o)},[p]),Ae=l.useCallback(()=>{p?(z(!1),L(null)):(z(!0),L(b))},[p,b]);l.useEffect(()=>{e&&s&&(d(0),z(!1),L(null))},[e,s]);const{data:u,isLoading:_,error:C,refetch:M,isFetching:X}=He({queryKey:["kline-5year",s,i,f,k],queryFn:async()=>{const o=await yt({symbol:s,period:i,years:Nt,forceRefresh:f});return f&&w(!1),o},enabled:e&&!!s,staleTime:f?0:10*60*1e3,gcTime:30*60*1e3,retry:3,retryDelay:o=>Math.min(1e3*2**o,3e4),refetchOnWindowFocus:!1}),m=(u==null?void 0:u.kline_data)||[],R=u==null?void 0:u.latest_price,Y=(u==null?void 0:u.name)||n||s,P=u==null?void 0:u.industry,j=u==null?void 0:u.data_range,W=(u==null?void 0:u.data_count)||0,N=l.useMemo(()=>{const o=p?h:b;if(o&&o.close!=null){const A=m.findIndex(H=>H.date===o.date),S=A>0?m[A-1].close:null,T=S!=null&&o.close!=null?o.close-S:null,B=S!=null&&S!==0&&T!=null?T/S*100:null,K=o.close!=null&&o.volume?o.close*o.volume/1e8:null;return{open:o.open,high:o.high,low:o.low,close:o.close,change:T,changePct:B,volume:o.volume,amount:K,date:o.date}}const y=m.length>0?m[m.length-1]:null;return R?{open:(y==null?void 0:y.open)??null,high:(y==null?void 0:y.high)??null,low:(y==null?void 0:y.low)??null,close:R.close,change:R.change,changePct:R.change_pct,volume:R.volume,amount:R.amount,date:null}:null},[p,h,b,R,m]),G=((N==null?void 0:N.change)||0)>=0,te=G?"text-red-500":"text-green-600",Ie=G?ot:rt,Ee=l.useCallback(async()=>{var o,y,A,S,T,B,K,H,le;if(!(!J.current||!s))try{const I=p?h:b,Q=(I==null?void 0:I.date)||(m.length>0?m[m.length-1].date:null),V=Q?m.findIndex(q=>q.date===Q):m.length-1,r=V>=0?m[V]:null,$=V>0?m[V-1]:null,Z=r!=null&&r.close&&($!=null&&$.close)?r.close-$.close:null,ce=Z!==null&&($!=null&&$.close)?Z/$.close*100:null,D=(Z??0)>=0,ee=await J.current.captureCharts(Q||void 0),Be=i==="day"?"日K線":i==="week"?"週K線":"月K線",F=window.open("","_blank","width=1123,height=794");if(F){const q=O(s),de=O(Y??""),me=P?O(P):"",ue=O(Be);F.document.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>${q} ${de} ${ue}</title>
                        <style>
                            @page { size: A4 landscape; margin: 8mm; }
                            * { box-sizing: border-box; margin: 0; padding: 0; }
                            body {
                                font-family: "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                                padding: 12px;
                                background: #fff;
                                -webkit-print-color-adjust: exact;
                                print-color-adjust: exact;
                            }
                            .container { width: 100%; max-width: 280mm; margin: 0 auto; }
                            .header {
                                display: flex; justify-content: space-between; align-items: flex-end;
                                margin-bottom: 10px; padding-bottom: 8px; border-bottom: 3px solid #000;
                            }
                            .title-group { display: flex; align-items: baseline; gap: 15px; }
                            .symbol { font-size: 28px; font-weight: 900; color: #000; }
                            .name { font-size: 20px; font-weight: bold; color: #333; }
                            .meta { color: #666; font-size: 11px; }
                            .info-section {
                                display: flex; gap: 10px; margin-bottom: 10px;
                            }
                            .price-grid {
                                display: flex; flex: 1; padding: 10px 15px;
                                background: #f1f5f9; border-radius: 8px; border: 1px solid #e2e8f0;
                            }
                            .price-item { text-align: center; flex: 1; border-right: 1px solid #cbd5e1; }
                            .price-item:last-child { border-right: none; }
                            .price-label { font-size: 11px; color: #64748b; margin-bottom: 3px; font-weight: 500; }
                            .price-value { font-size: 16px; font-weight: 800; }
                            .ma-grid {
                                display: flex; flex: 1; padding: 10px 15px;
                                background: #fefce8; border-radius: 8px; border: 1px solid #fef08a;
                            }
                            .ma-item { text-align: center; flex: 1; border-right: 1px solid #fde047; }
                            .ma-item:last-child { border-right: none; }
                            .ma-label { font-size: 11px; margin-bottom: 3px; font-weight: 600; }
                            .ma-value { font-size: 14px; font-weight: 700; }
                            .legend-row {
                                display: flex; align-items: center; gap: 15px; margin-bottom: 8px; padding: 6px 10px;
                                background: #f8fafc; border-radius: 6px; font-size: 11px;
                            }
                            .legend-item { display: flex; align-items: center; gap: 4px; }
                            .legend-box { width: 12px; height: 12px; border-radius: 2px; }
                            .up { color: #dc2626; }
                            .down { color: #16a34a; }
                            .chart-section { margin-bottom: 6px; }
                            .chart-image {
                                width: 100%; display: block; border: 1px solid #e5e7eb; border-radius: 4px;
                            }
                            .chart-label {
                                font-size: 10px; color: #64748b; margin-bottom: 2px; font-weight: 500;
                            }
                            .footer {
                                display: flex; justify-content: space-between; margin-top: 8px;
                                padding-top: 6px; border-top: 1px solid #eee; font-size: 10px; color: #94a3b8;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">
                                <div class="title-group">
                                    <span class="symbol">${q}</span>
                                    <span class="name">${de}</span>
                                    ${me?`<span style="font-size:12px; background:#eee; padding:2px 6px; border-radius:4px;">${me}</span>`:""}
                                    <span style="font-size:14px; background:#3b82f6; color:white; padding:3px 10px; border-radius:4px; font-weight:600;">${ue}</span>
                                </div>
                                <div class="meta">資料日期：${(r==null?void 0:r.date)||"-"}</div>
                            </div>

                            <!-- 價格資訊 + 均線資訊 -->
                            <div class="info-section">
                                <div class="price-grid">
                                    <div class="price-item">
                                        <div class="price-label">開盤價</div>
                                        <div class="price-value" style="color:#0f172a">${((o=r==null?void 0:r.open)==null?void 0:o.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="price-item">
                                        <div class="price-label">收盤價</div>
                                        <div class="price-value ${D?"up":"down"}">${((y=r==null?void 0:r.close)==null?void 0:y.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="price-item">
                                        <div class="price-label">最高價</div>
                                        <div class="price-value up">${((A=r==null?void 0:r.high)==null?void 0:A.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="price-item">
                                        <div class="price-label">最低價</div>
                                        <div class="price-value down">${((S=r==null?void 0:r.low)==null?void 0:S.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="price-item">
                                        <div class="price-label">漲跌幅</div>
                                        <div class="price-value ${D?"up":"down"}">${ce!==null?(D?"+":"")+ce.toFixed(2)+"%":"-"}</div>
                                    </div>
                                </div>
                                <div class="ma-grid">
                                    <div class="ma-item">
                                        <div class="ma-label" style="color:#ffc107">MA5</div>
                                        <div class="ma-value" style="color:#b38600">${((T=r==null?void 0:r.ma5)==null?void 0:T.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="ma-item">
                                        <div class="ma-label" style="color:#9c27b0">MA10</div>
                                        <div class="ma-value" style="color:#7b1fa2">${((B=r==null?void 0:r.ma10)==null?void 0:B.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="ma-item">
                                        <div class="ma-label" style="color:#2196f3">MA20</div>
                                        <div class="ma-value" style="color:#1565c0">${((K=r==null?void 0:r.ma20)==null?void 0:K.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="ma-item">
                                        <div class="ma-label" style="color:#ff9800">MA60</div>
                                        <div class="ma-value" style="color:#e65100">${((H=r==null?void 0:r.ma60)==null?void 0:H.toFixed(2))??"-"}</div>
                                    </div>
                                    <div class="ma-item">
                                        <div class="ma-label" style="color:#9e9e9e">MA120</div>
                                        <div class="ma-value" style="color:#616161">${((le=r==null?void 0:r.ma120)==null?void 0:le.toFixed(2))??"-"}</div>
                                    </div>
                                </div>
                            </div>

                            <!-- 圖例 -->
                            <div class="legend-row">
                                <div class="legend-item">
                                    <div class="legend-box" style="background:#ef5350"></div>
                                    <span>上漲</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-box" style="background:#26a69a"></div>
                                    <span>下跌</span>
                                </div>
                                <div style="width:1px; height:12px; background:#cbd5e1; margin:0 5px;"></div>
                                <div class="legend-item">
                                    <div class="legend-box" style="background:#ffc107"></div>
                                    <span>MA5</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-box" style="background:#9c27b0"></div>
                                    <span>MA10</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-box" style="background:#2196f3"></div>
                                    <span>MA20</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-box" style="background:#ff9800"></div>
                                    <span>MA60</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-box" style="background:#9e9e9e"></div>
                                    <span>MA120</span>
                                </div>
                            </div>

                            <!-- K線主圖（最大） -->
                            <div class="chart-section">
                                <div class="chart-label">K線圖</div>
                                <img src="${ee.main}" class="chart-image" />
                            </div>

                            <!-- 成交量圖 -->
                            <div class="chart-section">
                                <div class="chart-label">成交量</div>
                                <img src="${ee.volume}" class="chart-image" />
                            </div>

                            <!-- 技術指標圖 -->
                            <div class="chart-section">
                                <div class="chart-label">技術指標</div>
                                <img src="${ee.indicator}" class="chart-image" />
                            </div>

                            <div class="footer">
                                <span>資料來源：TWSE / FinMind (貓星人賺大錢系統)</span>
                                <span>資料範圍：${(j==null?void 0:j.first_date)||"-"} ~ ${(j==null?void 0:j.last_date)||"-"} (共 ${W} 筆)</span>
                            </div>
                        </div>
                    </body>
                    </html>
                `),F.document.close(),F.onload=()=>{setTimeout(()=>{F.focus(),F.print()},500)}}}catch(I){console.error("列印失敗:",I),alert("列印準備失敗，請重試")}},[s,Y,P,j,W,m,p,h,b,i]),Me=l.useCallback(()=>{w(!0),d(o=>o+1)},[]),se=l.useCallback(()=>{d(o=>o+1),M()},[M]);l.useEffect(()=>{f&&M()},[f,M]);const ae=l.useMemo(()=>jt[g],[g]),We=l.useMemo(()=>{if(!C)return null;const o=C instanceof Error?C.message:"發生未知錯誤";return o.includes("timeout")?"請求超時，已自動重試":o.includes("402")?"API 額度已用完，請稍候再試":o},[C]);return t.jsx(ft,{open:e,onOpenChange:o=>!o&&a(),children:t.jsxs(_e,{className:`${ae.dialogWidth} max-h-[95vh] overflow-y-auto transition-all duration-300 ease-in-out p-4 sm:p-5 focus:outline-none`,children:[t.jsx(Ce,{className:"no-print",children:t.jsxs(Re,{className:"flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pr-8",children:[t.jsxs("div",{className:"flex items-center gap-3",children:[t.jsx("span",{className:"font-mono text-base font-semibold bg-primary/10 text-primary px-2.5 py-1 rounded-lg",children:s}),t.jsx("span",{className:"text-lg font-bold",children:Y}),P&&t.jsx("span",{className:"text-xs text-muted-foreground px-2 py-0.5 bg-muted rounded-full",children:P})]}),t.jsxs("div",{className:"flex items-center gap-1.5",children:[t.jsxs(gt,{value:i,onValueChange:o=>c(o),children:[t.jsx(Le,{className:"w-18 h-7 text-xs",children:t.jsx(ht,{})}),t.jsx(Ue,{children:wt.map(o=>t.jsx(ze,{value:o.value,children:o.label},o.value))})]}),t.jsxs(E,{variant:"outline",size:"sm",onClick:Ee,className:"h-7 text-xs",disabled:_||m.length===0,children:[t.jsx(at,{className:"h-3.5 w-3.5 mr-1"}),"列印"]}),t.jsxs(E,{variant:p?"default":"outline",size:"sm",onClick:Ae,className:`h-7 text-xs ${p?"bg-amber-500 hover:bg-amber-600":""}`,disabled:_||m.length===0,children:[p?t.jsx(it,{className:"h-3.5 w-3.5 mr-1"}):t.jsx(nt,{className:"h-3.5 w-3.5 mr-1"}),p?`已鎖定 ${(h==null?void 0:h.date)||""}`:"鎖定"]}),t.jsx(E,{variant:"ghost",size:"icon",onClick:Me,className:"h-7 w-7",disabled:_||X,children:t.jsx(fe,{className:`h-4 w-4 ${_||X?"animate-spin":""}`})})]})]})}),N&&t.jsxs("div",{className:"grid grid-cols-5 gap-2 p-3 bg-gradient-to-r from-muted/50 to-accent/30 dark:from-muted/30 dark:to-accent/20 rounded-xl text-sm mb-2 ring-1 ring-border/30",children:[t.jsxs("div",{className:"text-center",children:[t.jsx("div",{className:"text-[10px] text-muted-foreground font-medium uppercase tracking-wider",children:"開盤"}),t.jsx("div",{className:"text-base font-bold font-mono tabular-nums",children:((ie=N.open)==null?void 0:ie.toFixed(2))??"-"})]}),t.jsxs("div",{className:"text-center",children:[t.jsx("div",{className:"text-[10px] text-muted-foreground font-medium uppercase tracking-wider",children:"收盤"}),t.jsx("div",{className:`text-base font-bold font-mono tabular-nums ${te}`,children:((ne=N.close)==null?void 0:ne.toFixed(2))??"-"})]}),t.jsxs("div",{className:"text-center",children:[t.jsx("div",{className:"text-[10px] text-muted-foreground font-medium uppercase tracking-wider",children:"最高"}),t.jsx("div",{className:"text-base font-bold text-red-500 font-mono tabular-nums",children:((oe=N.high)==null?void 0:oe.toFixed(2))??"-"})]}),t.jsxs("div",{className:"text-center",children:[t.jsx("div",{className:"text-[10px] text-muted-foreground font-medium uppercase tracking-wider",children:"最低"}),t.jsx("div",{className:"text-base font-bold text-green-600 font-mono tabular-nums",children:((re=N.low)==null?void 0:re.toFixed(2))??"-"})]}),t.jsxs("div",{className:"text-center",children:[t.jsx("div",{className:"text-[10px] text-muted-foreground font-medium uppercase tracking-wider",children:"漲跌幅"}),t.jsxs("div",{className:`text-base font-bold flex items-center justify-center font-mono tabular-nums ${te}`,children:[t.jsx(Ie,{className:"h-3 w-3 mr-0.5"}),N.changePct!=null?`${G?"+":""}${N.changePct.toFixed(2)}%`:"-"]})]})]}),j&&t.jsxs("div",{className:"flex items-center justify-between text-xs text-muted-foreground px-1 mb-2",children:[t.jsxs("div",{className:"flex items-center gap-1",children:[t.jsx(lt,{className:"h-3 w-3"}),j.first_date," ~ ",j.last_date," (",W.toLocaleString(),"筆)"]}),W>=1e3&&t.jsx("span",{className:"text-green-600",children:"✓ 5年完整"})]}),t.jsxs("div",{children:[_&&t.jsxs("div",{className:"flex flex-col items-center justify-center py-20",children:[t.jsx(ct,{className:"h-10 w-10 animate-spin text-primary"}),t.jsx("p",{className:"mt-3 text-muted-foreground",children:"載入 5 年資料中..."}),t.jsx("p",{className:"text-xs text-muted-foreground/60",children:"首次約需 30-60 秒"})]}),C&&t.jsxs("div",{className:"flex flex-col items-center justify-center py-20",children:[t.jsx(dt,{className:"h-10 w-10 text-amber-500 mb-2"}),t.jsx("p",{className:"text-amber-600 font-medium",children:"載入失敗"}),t.jsx("p",{className:"text-sm text-muted-foreground",children:We}),t.jsxs(E,{variant:"outline",onClick:se,className:"mt-3",children:[t.jsx(fe,{className:"h-4 w-4 mr-1"}),"重試"]})]}),!_&&!C&&m.length>0&&t.jsx(ut,{ref:J,data:m,symbol:s||"",isLoading:X,chartHeights:ae,onCrosshairMove:Pe,onChartClick:o=>{z(!0),L(o)}}),!_&&!C&&m.length===0&&t.jsxs("div",{className:"flex flex-col items-center justify-center py-20 text-muted-foreground",children:[t.jsx(mt,{className:"h-10 w-10 mb-2"}),t.jsx("p",{children:"無法取得資料"}),t.jsx(E,{variant:"outline",onClick:se,className:"mt-3",children:"重試"})]})]})]})})}export{Yt as S,Tt as a,Ft as b,At as c,Pt as d,It as e,Ut as f,zt as g,Et as h,Xt as i,Mt as j,Wt as k,Bt as l,Kt as m,Ht as n,Vt as o,qt as p,Ot as q,Jt as r};
