
## Gateway Probe

gateway health ok
dashboard without token status: 401
dashboard with token status: 200

## Simulator Build

simulator: iPhone 17 (52721F06-326E-4BB5-AC04-2055C05DA175)
```bash
xcodebuild -project /Users/anovik-air/cento/apps/ios/CentoMobile/CentoMobile.xcodeproj -scheme CentoMobile -destination platform=iOS\ Simulator\,id=52721F06-326E-4BB5-AC04-2055C05DA175 -derivedDataPath /Users/anovik-air/cento/workspace/runs/agent-work/26/DerivedData-simulator build 
```


## Simulator Install And Launch


## Physical Device Build Install Launch

physical iPhone: 00008130-000E68823E81001C
```bash
xcodebuild -project /Users/anovik-air/cento/apps/ios/CentoMobile/CentoMobile.xcodeproj -scheme CentoMobile -destination platform=iOS\,id=00008130-000E68823E81001C -derivedDataPath /Users/anovik-air/cento/workspace/runs/agent-work/26/DerivedData-device -allowProvisioningUpdates -allowProvisioningDeviceRegistration build 
```


ios mobile e2e ok: /Users/anovik-air/cento/workspace/runs/agent-work/26
