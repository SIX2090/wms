"""Actual vendored ZXing pixels/hint transitions; no WMS, DB, hardware or HTTP."""
from pathlib import Path
import shutil
import subprocess

import pytest


PROGRAM = r"""
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict');
const root=process.argv[1],scenario=process.argv[2];
const Z=require(path.join(root,'app/static/cdn/zxing-library-0.23.0.min.js'));
const source=fs.readFileSync(path.join(root,'app/templates/mobile_scan.html'),'utf8');
const begin=source.indexOf('    function stopBarcodeScanner()');
const end=source.indexOf('    function addHistory(',begin);
assert(begin>=0&&end>begin,'The real scanner handlers must be present');
const formats=['CODE_128','CODE_39','EAN_13','EAN_8','UPC_A','UPC_E','QR_CODE','DATA_MATRIX','PDF_417'].map(name=>Z.BarcodeFormat[name]);
const callbacks=[],timers=[],frames=[];
class ActualReader extends Z.BrowserMultiFormatReader {
  decodeFromVideoDevice(device,video,callback){callbacks.push(callback);return Promise.resolve();}
  // Translate the absent browser Canvas boundary to actual BinaryBitmap pixels.
  // The real browser reader, its hints setter and its decoder all remain in use.
  decode(bitmap){
    const hints=this.reader.hints;
    frames.push({hard:hints.get(Z.DecodeHintType.TRY_HARDER)===true,
      present:hints.has(Z.DecodeHintType.TRY_HARDER),
      formats:[...hints.get(Z.DecodeHintType.POSSIBLE_FORMATS)],
      firstOneD:this.reader.readers[0] instanceof Z.MultiFormatOneDReader});
    return this.decodeBitmap(bitmap);
  }
}
class NoDecodeAdapter {
  constructor(hints){this.receivedHints=hints;}
  reset(){}
  decodeFromVideoDevice(device,video,callback){callbacks.push(callback);return Promise.resolve();}
}
const element=()=>({hidden:true,value:'',srcObject:null,events:{},focus(){},addEventListener(name,fn){this.events[name]=fn;}});
const context={Map,Promise,Error,console:{warn(){},error(){},log(){}},document:{},window:{addEventListener(){}},
  ZXing:{...Z,BrowserMultiFormatReader:scenario==='no-decode-adapter'?NoDecodeAdapter:ActualReader},
  barcodeScanner:element(),barcodeVideo:element(),barcodeBtn:element(),closeBarcodeBtn:element(),scanCode:element(),zxingCodeReader:null,
  setTimeout(fn,delay){timers.push({fn,delay});return timers.length;},clearTimeout(){},setStatus(){},lookupMaterial(){throw Error('No business lookup is allowed in this isolated decoder contract');}};
vm.createContext(context);vm.runInContext(source.slice(begin,end),context);
context.barcodeBtn.events.click();
const timer=timers.find(item=>item.delay===100);assert(timer);timer.fn();
assert.equal(callbacks.length,1,'The real handler must keep its existing camera entry');
const reader=context.zxingCodeReader;
if(scenario==='no-decode-adapter'){
  assert(reader);assert.equal(context.barcodeScanner.hidden,false);
  assert.deepEqual(Array.from(reader.receivedHints.get(Z.DecodeHintType.POSSIBLE_FORMATS)),formats);
  console.log(JSON.stringify({passed:true,scenario,real_sdk_decoder:false,legacy_adapter_compatible:true}));
  process.exit(0);
}
function runs(widths){const pixels=[];let black=true;for(const width of widths){for(let i=0;i<width;i++)pixels.push(black?0:255);black=!black;}return pixels;}
function code128(text){const symbols=[104,...[...text].map(c=>c.charCodeAt(0)-32)];let check=104;for(let i=1;i<symbols.length;i++)check+=symbols[i]*i;symbols.push(check%103,106);return [...Array(10).fill(255),...symbols.flatMap(n=>runs(Z.Code128Reader.CODE_PATTERNS[n])),...Array(10).fill(255)];}
function code39(text){const chars='*'+text+'*',row=Array(10).fill(255);for(let n=0;n<chars.length;n++){const c=chars[n],mask=c==='*'?Z.Code39Reader.ASTERISK_ENCODING:Z.Code39Reader.CHARACTER_ENCODINGS[Z.Code39Reader.ALPHABET_STRING.indexOf(c)];for(let i=0;i<9;i++)row.push(...Array(mask&(1<<(8-i))?3:1).fill(i%2===0?0:255));if(n<chars.length-1)row.push(255);}return [...row,...Array(10).fill(255)];}
let eanParent=Z.EAN13Reader;while(!eanParent.L_PATTERNS)eanParent=Object.getPrototypeOf(eanParent);
function ean(text){const n=text.length,leftCount=n===13?6:4,start=n===13?7:4,row=Array(11).fill(255);row.push(0,255,0);for(let i=0;i<leftCount;i++){const digit=Number(text[(n===13?1:0)+i]),g=n===13&&(Z.EAN13Reader.FIRST_DIGIT_ENCODINGS[Number(text[0])]&(1<<(5-i)));row.push(...runs(g?[...eanParent.L_PATTERNS[digit]].reverse():eanParent.L_PATTERNS[digit]).map(x=>255-x));}row.push(255,0,255,0,255);for(let i=start;i<n;i++)row.push(...runs(eanParent.L_PATTERNS[Number(text[i])]));row.push(0,255,0,...Array(11).fill(255));return row;}
function barcode(row,top=false){const w=640,h=480,pixels=new Uint8ClampedArray(w*h).fill(255),x0=Math.floor((w-row.length*3)/2),y0=top?18:190;assert(x0>=0);for(let y=y0;y<y0+(top?12:100);y++)for(let x=0;x<row.length;x++)for(let n=0;n<3;n++)pixels[y*w+x0+x*3+n]=row[x];return {w,h,pixels};}
function rotate(image){const {w,h,pixels}=image,out=new Uint8ClampedArray(w*h);for(let y=0;y<h;y++)for(let x=0;x<w;x++)out[(w-x-1)*h+y]=pixels[y*w+x];return {w:h,h:w,pixels:out};}
// The browser's HTMLCanvasElementLuminanceSource supports rotation. This fixture
// provides the same real pixel transformation, while Node has no Canvas DOM.
class RotatingPixels extends Z.RGBLuminanceSource {
  constructor(image){super(image.pixels,image.w,image.h);this.image=image;}
  isRotateSupported(){return true;}
  rotateCounterClockwise(){return new RotatingPixels(rotate(this.image));}
}
let image,text,format;
if(scenario==='qr'){
  const w=640,h=480,size=220;image={w,h,pixels:new Uint8ClampedArray(w*h).fill(255)};
  text='WMS-ADAPTIVE-QR';format=Z.BarcodeFormat.QR_CODE;
  const matrix=new Z.QRCodeWriter().encode(text,format,size,size,new Map());
  for(let y=0;y<size;y++)for(let x=0;x<size;x++)if(matrix.get(x,y))image.pixels[(y+130)*w+x+210]=0;
}else if(scenario==='code39'){text='WMS123';format=Z.BarcodeFormat.CODE_39;image=barcode(code39(text));}
else if(scenario==='ean13'){text='6901234567892';format=Z.BarcodeFormat.EAN_13;image=barcode(ean(text));}
else if(scenario==='ean8'){text='12345670';format=Z.BarcodeFormat.EAN_8;image=barcode(ean(text));}
else{text='WMS260001';format=Z.BarcodeFormat.CODE_128;image=barcode(code128(text),scenario==='off-center');if(scenario==='rotated')image=rotate(image);}
function bitmap(){return new Z.BinaryBitmap(new Z.HybridBinarizer(new RotatingPixels(image)));}
const originalWarn=console.warn,originalError=console.error;console.warn=()=>{};console.error=()=>{};
const results=[];
try {
  for(let i=0;i<8;i++){
    try{const result=reader.decode(bitmap());results.push({text:result.getText(),format:result.getBarcodeFormat()});}
    catch(error){assert(['NotFoundException','ChecksumException','FormatException'].includes(error.getKind?.()),String(error));results.push(null);}
  }
}finally{console.warn=originalWarn;console.error=originalError;}
assert.equal(frames.length,8);
for(let i=0;i<frames.length;i++){
  const strong=i%4===3,frame=frames[i];
  assert.equal(frame.hard,strong,'Frame '+(i+1)+' must use '+(strong?'the unchanged strong hints':'fast hints'));
  assert.equal(frame.present,strong,'Fast mode must remove TRY_HARDER, not set it false');
  assert.equal(frame.firstOneD,!strong,'Fast mode must put the actual 1D decoder first');
  assert.deepEqual(frame.formats,formats,'Every frame must retain all nine existing formats');
}
if(scenario==='off-center'||scenario==='rotated'){
  for(let i=0;i<results.length;i++)assert.equal(!!results[i],i%4===3,'The original strengthened pass must remain reachable every fourth frame');
}else assert(results.every(Boolean),'Clear real pixels must decode in fast and strengthened modes');
for(const result of results.filter(Boolean)){assert.equal(result.text,text);assert.equal(result.format,format);}
console.log(JSON.stringify({passed:true,scenario,real_sdk_decoder:true,frames,results,rotation_fixture:'actual pixel rotation, not a fake decoder result'}));
"""


@pytest.mark.parametrize('scenario', [
    'reader-order', 'code39', 'ean13', 'ean8', 'qr', 'off-center', 'rotated', 'no-decode-adapter',
])
def test_actual_zxing_adaptive_scan_frames(scenario):
    root = Path(__file__).resolve().parents[1]
    node = shutil.which('node')
    assert node, 'Node is required for the actual vendored ZXing contract'
    result = subprocess.run(
        [node, '--max-old-space-size=96', '--require',
         str(root / 'tests/audit_regressions/network_guard.cjs'),
         '-e', PROGRAM, str(root), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout
