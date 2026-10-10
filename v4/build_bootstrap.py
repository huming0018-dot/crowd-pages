#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-time v4 Mac updater bootstrap; no invitation, enrollment or policy edits."""
import argparse,hashlib,importlib.util,json,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('updates',root/'build_update.py');updates=importlib.util.module_from_spec(spec);spec.loader.exec_module(updates)
def build(source,helper,output,postprocess=None,vision=None,speech=None,multiplatform=None):
    architectures=subprocess.check_output(['lipo','-archs',str(helper)],text=True).split()
    if set(architectures)!={'x86_64','arm64'}:raise ValueError('Universal macOS helper required')
    subprocess.run(['codesign','--verify','--strict',str(helper)],check=True,capture_output=True)
    with tempfile.TemporaryDirectory() as d:
        temporary=pathlib.Path(d)/'base.zip';updates.build(source,temporary)
        with zipfile.ZipFile(temporary) as z:files={n:z.read(n) for n in z.namelist()}
    prefix='Mac众包更新/'
    version=json.loads(files[prefix+'插件/manifest.json'])['version']
    if version.split('.')[:2]!=['4','2']:raise ValueError('Updater bootstrap requires v4.2')
    files[prefix+'updater/crowd-v4-updater']=pathlib.Path(helper).read_bytes()
    if multiplatform is not None:
        for name in ('mc_runner.py','dashboard.py','dashboard.html','打开工作台.command','README.md'):
            files[prefix+'多平台采集/'+name]=(pathlib.Path(multiplatform)/name).read_bytes()
    if postprocess is not None:
        if vision is None or speech is None:raise ValueError('Compiled Vision and Speech tools required')
        for name in ('evidence.py','media.py','pipeline.py','local_asr.py','fetch_model.py','requirements-asr.txt','vision.swift','speech.swift','SpeechInfo.plist','README.md'):
            files[prefix+'授权文件后处理/'+name]=(pathlib.Path(postprocess)/name).read_bytes()
        if set(subprocess.check_output(['lipo','-archs',str(vision)],text=True).split())!={'x86_64','arm64'}:raise ValueError('Universal Vision tool required')
        subprocess.run(['codesign','--verify','--strict',str(vision)],check=True,capture_output=True)
        files[prefix+'授权文件后处理/crowd-vision']=pathlib.Path(vision).read_bytes()
        if set(subprocess.check_output(['lipo','-archs',str(speech)],text=True).split())!={'x86_64','arm64'}:raise ValueError('Universal Speech tool required')
        subprocess.run(['codesign','--verify','--strict',str(speech)],check=True,capture_output=True)
        files[prefix+'授权文件后处理/crowd-speech']=pathlib.Path(speech).read_bytes()
    files[prefix+'先打开安装说明.html']=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>接通自动更新 {version}</title><h1>一次接通，以后自动更新</h1><p>适用于 macOS 14 或以上，支持 Intel 和 Apple 芯片；请保留浏览器开发者模式。</p><p>在最初参加的 Mac、浏览器和个人资料运行“更新.command”，然后在打开的扩展管理页刷新原插件一次。不要卸载或重新报名。</p><p>本次会更新原插件并安装系统定时 OTA 和失败恢复任务。系统每小时独立检查签名版本：浏览器运行时下载验证缓存，由插件保存状态后加载；浏览器关闭时可更新文件，等待下次启动确认。只更新本插件，不关闭浏览器。保留参与身份、停止状态和未回传证据。插件内可关闭自动更新。</p><p>本版增加小红书KOL观察与B站采集，需要在原扩展管理页确认刷新及新的B站站点权限。旧自动更新助手会拒绝静默扩权，这是本次需要手动确认的原因；不卸载、不重新报名。不会修改浏览器管理策略或收集其他标签页。更新助手不执行远程任意脚本。首次接通仍需本次刷新，之后无需反复解压。</p><p>诊断开启时保留最近24个固定动作节点帮助定位故障，不发送Cookie、完整网址或正文。自动更新机制已做隔离实机验证，原设备真实采集仍须核验。</p></html>'''.encode()
    files.pop(prefix+'SHA256SUMS.txt')
    files[prefix+'SHA256SUMS.txt']=''.join(hashlib.sha256(b).hexdigest()+'  '+n.removeprefix(prefix)+'\n' for n,b in sorted(files.items())).encode()
    output=pathlib.Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(files.items()):
            i=zipfile.ZipInfo(n,(2026,10,8,0,0,0));i.create_system=3;i.external_attr=(0o100755 if n.endswith('.command') or n.endswith('/crowd-v4-updater') or n.endswith('/crowd-vision') or n.endswith('/crowd-speech') else 0o100644)<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,b)
    digest=hashlib.sha256(output.read_bytes()).hexdigest();output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n')
    return {'version':version,'bytes':output.stat().st_size,'sha256':digest,'mode':'one_time_updater_bootstrap'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--helper',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--postprocess',type=pathlib.Path);p.add_argument('--vision',type=pathlib.Path);p.add_argument('--speech',type=pathlib.Path);p.add_argument('--multiplatform',type=pathlib.Path);a=p.parse_args();print(json.dumps(build(a.source,a.helper,a.output,a.postprocess,a.vision,a.speech,a.multiplatform)))
